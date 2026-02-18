from flask import Blueprint, jsonify, request
from database import oracle, chatwoot
from dotenv import load_dotenv
from datetime import datetime
from auth import token_required
import re
load_dotenv()

crm_bp = Blueprint('crm', __name__)

def processar_obs_memo(obs_memo):
    """
    Processa o campo obs_memo e retorna uma lista de dicionários
    com data, usuario e observação, preservando quebras de linha
    """
    if not obs_memo:
        return []
    
    # Padrão regex para capturar: [Alteracao de obs em:DD/MM/YYYY   Usuario logado:USUARIO]
    pattern = r'\[Alteracao de obs em:(\d{2}/\d{2}/\d{4})\s+Usuario logado:([^\]]+)\]'
    
    # Encontrar todas as ocorrências do padrão
    matches = list(re.finditer(pattern, obs_memo))
    
    observacoes = []
    
    for i, match in enumerate(matches):
        data_str = match.group(1)  # DD/MM/YYYY
        usuario = match.group(2).strip()
        
        # Converter data de DD/MM/YYYY para YYYY-MM-DD
        try:
            data_obj = datetime.strptime(data_str, '%d/%m/%Y')
            data_iso = data_obj.strftime('%Y-%m-%d')
        except:
            data_iso = data_str
        
        # Encontrar o texto da observação
        start_pos = match.end()
        
        # Se há uma próxima alteração, o texto vai até ela
        if i + 1 < len(matches):
            end_pos = matches[i + 1].start()
        else:
            end_pos = len(obs_memo)
        
        observacao_texto = obs_memo[start_pos:end_pos]
        
        # Limpar apenas os \r e espaços no início/fim, mas manter \n
        # observacao_texto = observacao_texto.replace('\r', '')
        observacao_texto = observacao_texto.strip()
        
        if observacao_texto:  # Só adiciona se há texto
            observacoes.append({
                'data': data_iso,
                'usuario': usuario,
                'observacao': observacao_texto
            })
    
    return observacoes

@crm_bp.route('/api/eventos_atrasados', methods=['GET'])
def get_eventos_atrasados():
    try:
        conn_oracle, cur_oracle = oracle()
        retorno = {}
        now  = datetime.now().strftime("%Y-%m-%d")
        
        query = f"""
            SELECT 
            cg.cod_grupo, 
            cg.desc_grupo, 
            cet.COD_TIPO_EVENTO, 
            cet.DESC_TIPO_EVENTO, 
            count(*) eventos,
            ROUND(RATIO_TO_REPORT(COUNT(*)) OVER () * 100, 2) AS percentual
        FROM crm_eventos ce
        LEFT JOIN CRM_EVENTOS_TIPO cet ON 1=1
            AND cet.COD_TIPO_EVENTO = ce.COD_TIPO_EVENTO
        LEFT JOIN CRM_GRUPO cg ON 1=1
            AND cg.COD_GRUPO = cet.COD_GRUPO 
        WHERE 1=1
            AND ce.COD_EMPRESA IN (11,33)
            AND ce.status <> 'E' 
            and ce.status <> 'D'
            AND TRUNC(
                    CASE
                        WHEN ce.data_novo_contato IS NULL
                        THEN ce.data_evento
                        ELSE ce.data_novo_contato
                    END
                    ) < TO_DATE('{now}', 'YYYY-MM-DD')
        GROUP BY cg.cod_grupo, cg.desc_grupo, cet.COD_TIPO_EVENTO, cet.DESC_TIPO_EVENTO 
        ORDER BY 2
        """
        cur_oracle.execute(query)
        rows = cur_oracle.fetchall()
        if len(rows) == 0:
            return jsonify({'status': 'error', 'message': 'Não tem eventos pendentes'}), 404
        retorno['eventos_pendentes'] = []
        for row in rows:
            retorno['eventos_pendentes'].append({
                'cod_grupo': row[0],
                'desc_grupo': row[1],
                'cod_tipo_evento': row[2],
                'desc_tipo_evento': row[3],
                'eventos': row[4],
                'percentual': float(row[5])
            })
        cur_oracle.close()
        conn_oracle.close()
        return jsonify(retorno), 200
            
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@crm_bp.route('/api/crm/crm_andamentos', methods=['GET'])
@token_required
def get_crm_andamentos():
    try:
        query = f"""
            SELECT ca.COD_ANDAMENTO, ca.ANDAMENTO  
            FROM crm_andamento ca
            WHERE 1=1
                AND ca.ATIVO = 'S'
        """
        conn_oracle, cur_oracle = oracle()
        cur_oracle.execute(query)
        rows = cur_oracle.fetchall()
        if len(rows) == 0:
            return jsonify({'status': 'error', 'message': 'Não tem andamentos cadastrados'}), 404
        retorno = {'andamentos': []}
        for row in rows:
            retorno['andamentos'].append({
                'cod_andamento': row[0],
                'andamento': row[1]
            })
        return jsonify(retorno), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
        
@crm_bp.route('/api/crm/eventos_showroom/muda_andamento/<int:id_evento>', methods=['POST'])
@token_required
def muda_andamento_evento_showroom(id_evento):
    try:
        token_data = request.token_data
        email = token_data.get('email').strip().lower()
        cod_empresa = str(id_evento)[:2]
        cod_andamento = request.json.get('cod_andamento', None)
        if cod_empresa not in ['11', '33']:
            return jsonify({'status': 'error', 'message': 'ID do evento inválido'}), 400
        cod_evento = str(id_evento)[2:]
        if not cod_evento.isdigit():
            return jsonify({'status': 'error', 'message': 'ID do evento inválido'}), 400
        conn_oracle, cur_oracle = oracle()

        query = f"""
            SELECT cod_empresa,eu.nome 
            FROM empresas_usuarios eu
            LEFT JOIN SISTEMA_ACESSO_FUNCAO saf ON 1=1
                AND saf.COD_FUNCAO = eu.COD_FUNCAO 
            WHERE 1=1
                AND eu.DEMITIDO <> 'S'
                AND lower(eu.EMAIl) = '{email}'
            GROUP BY eu.COD_EMPRESA, eu.nome
            ORDER BY eu.cod_empresa
        """
        cur_oracle.execute(query)
        rows = cur_oracle.fetchall()
        quem_remarcou = rows[0][1]
        query = f"""
            select andamento from crm_andamento
            where 1=1
                and cod_andamento = {cod_andamento}
        """
        cur_oracle.execute(query)
        row = cur_oracle.fetchall()
        if len(row) == 0:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'Andamento inválido'}), 400
        nome_evento = row[0][0]
        query = f"""
            select count(*) from crm_eventos
            where 1=1
                and cod_empresa = {cod_empresa}
                and cod_evento = {cod_evento}
        """
        cur_oracle.execute(query)
        row = cur_oracle.fetchone()
        if row[0] == 0:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'Evento não encontrado'}), 404
        query = f"""
            update crm_eventos set cod_andamento = {cod_andamento}
            where 1=1
                and cod_empresa = {cod_empresa}
                and cod_evento = {cod_evento}
        """
        cur_oracle.execute(query)
        query = f"""
            insert into crm_acoes
            (cod_empresa,cod_evento, responsavel, tipo_acao, data, observacao, status, cod_acao, quem_criou)
            values (
                {cod_empresa},
                {cod_evento},
                '{quem_remarcou}',
                1,
                SYSDATE,
                'Mudança de andamento para: {nome_evento}',
                'P',
                seq_crm_COD_ACAO.nextval,
                '{quem_remarcou}')
        """
        # return query
        cur_oracle.execute(query)
        conn_oracle.commit()
        cur_oracle.close()
        conn_oracle.close()
        retorno = {}
        retorno['message'] = 'Andamento atualizado com sucesso'
        return jsonify(retorno), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@crm_bp.route('/api/crm/eventos', methods=['GET'])
@token_required
def list_crm_eventos():
    try:
        now = datetime.now().strftime("%Y-%m-%d")
        list_status = ['P','E','D','V','A','R','CP']
        token_data = request.token_data
        email = token_data.get('email').strip().lower()
        status = request.args.get('status', None)
        tipo_evento = request.args.get('tipo_evento', None)
        initial_date = request.args.get('initial_date', None)
        final_date = request.args.get('final_date', None)
        current_page = int(request.args.get('current_page', 1))
        search = request.args.get('search', None)
        responsible = request.args.get('responsible', None)
        limit = int(request.args.get('limit', 100))
        retorno = {}
        
        filter_tipo_evento = ''
        if tipo_evento:
            tipo_evento = tipo_evento.split(',')
            for te in tipo_evento:
                if not te.isdigit():
                    return jsonify({'status': 'error', 'message': f'Tipo de evento inválido: {te}'}), 400
            tipo_evento = ",".join(tipo_evento)
            filter_tipo_evento = f" AND ce.COD_TIPO_EVENTO IN ({tipo_evento}) "
        
        filter_initial_date = ''
        filter_final_date = ''
        if initial_date:
            try:
                datetime.strptime(initial_date, '%Y-%m-%d')
                filter_initial_date = f" AND TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) >= TO_DATE('{initial_date}', 'YYYY-MM-DD') "
            except ValueError:
                return jsonify({'status': 'error', 'message': 'Data inicial inválida. Use o formato YYYY-MM-DD'}), 400
        
        if final_date:
            try:
                datetime.strptime(final_date, '%Y-%m-%d')
                filter_final_date = f" AND TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) <= TO_DATE('{final_date}', 'YYYY-MM-DD')"
            except ValueError:
                return jsonify({'status': 'error', 'message': 'Data final inválida. Use o formato YYYY-MM-DD'}), 400
        
        
        filter_status = ''
        if status:
            status = status.split(',')
            for s in status:
                if s not in list_status:
                    return jsonify({'status': 'error', 'message': f'Status inválido: {s}'}), 400
            status = "','".join(status)
            status = f"('{status}')"
            status = status.replace("''","'")
            status = status.replace("'(","(")
            status = status.replace(")'",")")
            filter_status = f""" AND (
                                CASE
                                    WHEN ce.cod_motivo_perda IS NOT NULL AND ce.status = 'E' THEN 'CP'
                                    ELSE ce.status
                                END
                            ) IN {status}"""
        
        if search:
            search = search.replace("'", "''").lower()
            filter_search = f"""
                AND (
                    LOWER(ce.RESPONSAVEL_PELO_EVENTO) LIKE '%{search.lower()}%'
                    OR LOWER(ce.NOME_CLIENTE_AVULSO) LIKE '%{search.lower()}%'
                    OR LOWER(c.NOME) LIKE '%{search.lower()}%'
                    OR LOWER(c.EMAIL_NFE) LIKE '%{search.lower()}%'
                    OR LOWER(ce.EMAIL_CLIENTE_AVULSO) LIKE '%{search.lower()}%'
                    OR LOWER(ce.FONE_CLIENTE_AVULSO) LIKE '%{search.lower()}%'
                    OR LOWER(concat(c.PREFIXO_CEL,c.TELEFONE_CEL)) LIKE '%{search.lower()}%'
                    OR LOWER(concat(c.PREFIXO_RES,c.TELEFONE_RES)) LIKE '%{search.lower()}%'
                    OR LOWER(concat(c.PREFIXO_COM,c.TELEFONE_COM)) LIKE '%{search.lower()}%'
                    OR LOWER(concat(c.PREFIXO_FAX,c.TELEFONE_FAX)) LIKE '%{search.lower()}%'
                    OR LOWER(concat(c.PREFIXO_MSG_TXT_INST,c.NUMERO_MSG_TXT_INST)) LIKE '%{search.lower()}%'
                    OR LOWER(pm.DESCRICAO_MODELO) LIKE '%{search.lower()}%'
                    OR TO_CHAR(ce.COD_EVENTO) = '{search}'
                )
            """
        
        
        
        query = f"""
            SELECT saf.COD_ACESSO 
            FROM empresas_usuarios eu
            LEFT JOIN SISTEMA_ACESSO_FUNCAO saf ON 1=1
                AND saf.COD_FUNCAO = eu.COD_FUNCAO 
            WHERE 1=1
                AND eu.DEMITIDO <> 'S'
                AND lower(eu.EMAIl) = '{email}'
                AND saf.COD_ACESSO = '80320'
            GROUP BY saf.COD_ACESSO
        """
        conn_oracle, cur_oracle = oracle()
        cur_oracle.execute(query)
        rows = cur_oracle.fetchall()
        filter_responsavel = ''
        if len(rows) == 0:
            filter_responsavel = f" AND lower(eu.EMAIl) = '{email}' "
        if filter_responsavel == '' and responsible:
            responsible_list = responsible.split(',')
            responsible_emails = "','".join([r.strip().lower() for r in responsible_list])
            filter_responsavel = f" AND lower(eu.EMAIl) IN ('{responsible_emails}') "
        
        query = f"""
                SELECT
                    count(*)
                FROM
                    CRM_EVENTOS ce
                LEFT JOIN EMPRESAS_USUARIOS eu ON
                    1 = 1
                    AND eu.nome = ce.RESPONSAVEL_PELO_EVENTO
                LEFT JOIN CRM_ANDAMENTO ca ON
                    1 = 1
                    AND ca.COD_ANDAMENTO = ce.COD_ANDAMENTO
                LEFT JOIN MIDIA m ON
                    1=1
                    AND m.COD_MIDIA = ce.COD_MIDIA 
                LEFT JOIN clientes c ON
                    1 = 1
                    AND ce.COD_CLIENTE = c.COD_CLIENTE
                LEFT JOIN CRM_EVENTOS_TIPO cet ON 1=1
                    AND cet.COD_TIPO_EVENTO = ce.COD_TIPO_EVENTO
                LEFT JOIN CRM_DESCARTES cd on 1=1
                    and cd.COD_DESCARTE = ce.COD_DESCARTE
                LEFT JOIN CRM_MOTIVO_PERDAS cmp ON 1=1
                    AND cmp.cod_motivo_perda = ce.cod_motivo_perda
                LEFT JOIN produtos_modelos pm ON pm.COD_PRODUTO = ce.COD_PRODUTO AND pm.COD_MODELO = ce.COD_MODELO 
                WHERE
                    1 = 1
                    --AND ce.COD_TIPO_EVENTO IN (785)
                    {filter_responsavel}
                    {filter_status}
                    {filter_search if search else ''}
                    {filter_initial_date}
                    {filter_final_date}
                    {filter_tipo_evento}
                    --AND TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) >= TO_DATE('{initial_date}', 'YYYY-MM-DD')
                    --AND TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) <= TO_DATE('{final_date}', 'YYYY-MM-DD')
        """
        # return query
        cur_oracle.execute(query)
        total = cur_oracle.fetchone()[0]
        if total == 0:
            return jsonify({'status': 'error', 'message': 'Não tem eventos showroom no período'}), 404
        offset = (current_page - 1) * limit
        total_pages = (total + limit - 1) // limit
        start_row = (current_page - 1) * limit + 1
        end_row = current_page * limit
        if current_page > total_pages:
            return jsonify({'status': 'error', 'message': 'Página inválida'}), 400
        query =f"""
            SELECT *
            FROM (
                SELECT t.*, ROWNUM AS rn
                FROM (
                    -- Sua query original com ORDER BY aqui dentro
                    SELECT
                        CASE
                            WHEN ce.cod_motivo_perda IS NOT null AND ce.status = 'E' THEN 'CP'
                            ELSE ce.status
                        END status,
                        TO_CHAR(ce.DATA_CRIACAO, 'YYYY-MM-DD HH24:MI:SS') AS DATA_CRIACAO,
                        TO_CHAR(
                            CASE
                                WHEN ce.data_novo_contato IS NULL THEN ce.data_evento
                                ELSE ce.data_novo_contato
                            END, 'YYYY-MM-DD HH24:MI:SS'
                        ) AS data_contato,
                        ce.COD_EVENTO,
                        ce.COD_EMPRESA,
                        cet.DESC_TIPO_EVENTO,
                        ca.ANDAMENTO,
                        ce.COD_CLIENTE,
                        CASE
                            WHEN ce.COD_CLIENTE = 1 THEN ce.NOME_CLIENTE_AVULSO 
                            ELSE c.NOME 
                        END nome_cliente,
                        concat(c.PREFIXO_CEL,c.TELEFONE_CEL) tel_cel,
                        ce.fone_cliente_avulso,
                        ce.email_cliente_avulso,
                        c.EMAIL_NFE,
                        ce.TERMOMETRO,
                        ce.OBS_MEMO,
                        cmp.desc_motivo motivo_perda,
                        cd.descricao_descarte,
                        ce.RESPONSAVEL_PELO_EVENTO,
                        eu.NOME_COMPLETO RESPONSAVEL_NOME_COMPLETO,
                        pm.descricao_modelo,
                        concat(c.PREFIXO_RES,c.TELEFONE_RES) tel_residencial,
                        concat(c.PREFIXO_COM,c.TELEFONE_COM) tel_comercial,
                        concat(c.PREFIXO_FAX,c.TELEFONE_FAX) tel_fax,
                        concat(c.PREFIXO_MSG_TXT_INST,c.NUMERO_MSG_TXT_INST) tel_whatsapp,
                        ce.data_agendada,
                        ce.data_visita,
                        CASE
			                -- Se a data/hora do contato for anterior a data/hora atual, está ATRASADO
			                WHEN (
			                    CASE
			                        WHEN ce.data_novo_contato IS NULL THEN ce.data_evento
			                        ELSE ce.data_novo_contato
			                    END
			                ) < SYSDATE THEN 'ATRASADO'
			                -- Se a data do contato (ignorando a hora) for maior que a data de hoje, é Futuro
			                WHEN TRUNC(
			                    CASE
			                        WHEN ce.data_novo_contato IS NULL THEN ce.data_evento
			                        ELSE ce.data_novo_contato
			                    END
			                ) > TRUNC(SYSDATE) THEN 'FUTURO'
			                -- Caso contrário, é para hoje (de agora até o fim do dia)
			                ELSE 'TRABALHANDO'
			            END AS status_atendimento
                    FROM
                        CRM_EVENTOS ce
                    LEFT JOIN EMPRESAS_USUARIOS eu ON eu.nome = ce.RESPONSAVEL_PELO_EVENTO
                    LEFT JOIN CRM_ANDAMENTO ca ON ca.COD_ANDAMENTO = ce.COD_ANDAMENTO
                    LEFT JOIN MIDIA m ON m.COD_MIDIA = ce.COD_MIDIA 
                    LEFT JOIN clientes c ON ce.COD_CLIENTE = c.COD_CLIENTE
                    LEFT JOIN CRM_EVENTOS_TIPO cet ON cet.COD_TIPO_EVENTO = ce.COD_TIPO_EVENTO
                    LEFT JOIN CRM_DESCARTES cd on cd.COD_DESCARTE = ce.COD_DESCARTE
                    LEFT JOIN CRM_MOTIVO_PERDAS cmp ON cmp.cod_motivo_perda = ce.cod_motivo_perda
                    LEFT JOIN produtos_modelos pm ON pm.COD_PRODUTO = ce.COD_PRODUTO AND pm.COD_MODELO = ce.COD_MODELO 
                    WHERE
                        1 = 1
                        --AND ce.COD_TIPO_EVENTO IN (785)
                        {filter_tipo_evento}
                        {filter_responsavel}
                        {filter_status}
                        {filter_search if search else ''}
                        {filter_initial_date}
                        {filter_final_date}
                        --AND TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) >= TO_DATE('{initial_date}', 'YYYY-MM-DD')
                        --AND TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) <= TO_DATE('{final_date}', 'YYYY-MM-DD')
                    ORDER BY
                        3 asc
                ) t
            )
            WHERE
                rn BETWEEN {start_row} AND {end_row}
        """
        # return query
        cur_oracle.execute(query)
        rows = cur_oracle.fetchall()
        retorno['total_eventos'] = total
        retorno['total_pages'] = total_pages
        retorno['current_page'] = current_page
        retorno['eventos'] = []
        for row in rows:
            if row[1]:  # data_criacao
                try:
                    data_criacao_obj = datetime.strptime(row[1], '%Y-%m-%d %H:%M:%S')
                    data_criacao_iso = data_criacao_obj.isoformat()
                except:
                    data_criacao_iso = row[1]  # fallback para string original
            
            if row[2]:  # data_contato
                try:
                    data_contato_obj = datetime.strptime(row[2], '%Y-%m-%d %H:%M:%S')
                    data_contato_iso = data_contato_obj.isoformat()
                except:
                    data_contato_iso = row[2]  # fallback para string original
            if row[24]:  # data_agendada
                try:
                    data_agendada_obj = datetime.strptime(row[24], '%Y-%m-%d %H:%M:%S')
                    data_agendada_iso = data_agendada_obj.isoformat()
                except:
                    data_agendada_iso = row[24]  # fallback para string original
            if row[25]:  # data_visita
                try:
                    data_visita_obj = datetime.strptime(row[25], '%Y-%m-%d %H:%M:%S')
                    data_visita_iso = data_visita_obj.isoformat()
                except:
                    data_visita_iso = row[25]  # fallback para string original
            obs_memo_processado = processar_obs_memo(row[14])

            retorno['eventos'].append({  
                'status': row[0],
                'data_criacao': data_criacao_iso,
                'data_contato': data_contato_iso,
                'cod_evento': row[3],
                'cod_empresa': row[4],
                'desc_tipo_evento': row[5],
                'andamento': row[6],
                'cod_cliente': row[7],
                'nome_cliente': row[8],
                'tel_cel': row[9],
                'fone_cliente_avulso': row[10],
                'email_cliente_avulso': row[11],
                'email_nfe': row[12],
                'termometro': row[13],
                'obs_memo': obs_memo_processado,
                'motivo_perda': row[15],
                'descricao_descarte': row[16],
                'responsavel_pelo_evento': row[17],
                'responsavel_nome_completo': row[18],
                'descricao_modelo': row[19],
                'tel_residencial': row[20],
                'tel_comercial': row[21],
                'tel_fax': row[22],
                'tel_whatsapp': row[23],
                'data_agendada': data_agendada_iso if row[24] else None,
                'data_visita': data_visita_iso if row[25] else None,
                'status_atendimento': row[26]
            })
        cur_oracle.close()
        conn_oracle.close()

        return jsonify(retorno), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@crm_bp.route('/api/crm/eventos/<int:id_evento>', methods=['GET'])
@token_required
def show_crm_eventos(id_evento):
    try:
        retorno = {}
        token_data = request.token_data
        # return 'aqui'
        email = token_data.get('email').strip().lower()
        cod_empresa = str(id_evento)[:2]
        if cod_empresa not in ['11', '33']:
            return jsonify({'status': 'error', 'message': 'ID do evento inválido'}), 400
        cod_evento = str(id_evento)[2:]
        if not cod_evento.isdigit():
            return jsonify({'status': 'error', 'message': 'ID do evento inválido'}), 400
        cod_evento = int(cod_evento)
        
        query = f"""
            SELECT saf.COD_ACESSO 
            FROM empresas_usuarios eu
            LEFT JOIN SISTEMA_ACESSO_FUNCAO saf ON 1=1
                AND saf.COD_FUNCAO = eu.COD_FUNCAO 
            WHERE 1=1
                AND eu.DEMITIDO <> 'S'
                AND lower(eu.EMAIl) = '{email}'
                AND saf.COD_ACESSO = '80320'
            GROUP BY saf.COD_ACESSO
        """
        conn_oracle, cur_oracle = oracle()
        cur_oracle.execute(query)
        rows = cur_oracle.fetchall()
        filter_responsavel = ''
        if len(rows) == 0:
            filter_responsavel = f" AND lower(eu.EMAIl) = '{email}' "
        
        query = f"""
                SELECT
                        CASE
                            WHEN ce.cod_motivo_perda IS NOT null AND ce.status = 'E' THEN 'CP'
                            ELSE ce.status
                        END status,
                        TO_CHAR(ce.DATA_CRIACAO, 'YYYY-MM-DD HH24:MI:SS') AS DATA_CRIACAO,
                        TO_CHAR(
                            CASE
                                WHEN ce.data_novo_contato IS NULL THEN ce.data_evento
                                ELSE ce.data_novo_contato
                            END, 'YYYY-MM-DD HH24:MI:SS'
                        ) AS data_contato,
                        ce.COD_EVENTO,
                        ce.COD_EMPRESA,
                        cet.DESC_TIPO_EVENTO,
                        ca.ANDAMENTO,
                        ce.COD_CLIENTE,
                        CASE
                            WHEN ce.COD_CLIENTE = 1 THEN ce.NOME_CLIENTE_AVULSO 
                            ELSE c.NOME 
                        END nome_cliente,
                        concat(c.PREFIXO_CEL,c.TELEFONE_CEL) tel_cel,
                        ce.fone_cliente_avulso,
                        ce.email_cliente_avulso,
                        c.EMAIL_NFE,
                        ce.TERMOMETRO,
                        ce.OBS_MEMO,
                        cmp.desc_motivo motivo_perda,
                        cd.descricao_descarte,
                        ce.RESPONSAVEL_PELO_EVENTO,
                        eu.NOME_COMPLETO RESPONSAVEL_NOME_COMPLETO,
                        pm.descricao_modelo,
                        concat(c.PREFIXO_RES,c.TELEFONE_RES) tel_residencial,
                        concat(c.PREFIXO_COM,c.TELEFONE_COM) tel_comercial,
                        concat(c.PREFIXO_FAX,c.TELEFONE_FAX) tel_fax,
                        concat(c.PREFIXO_MSG_TXT_INST,c.NUMERO_MSG_TXT_INST) tel_whatsapp,
                        ce.COD_MIDIA,
                        m.DESCRICAO,
                        ce.data_agendada,
                        ce.data_visita,
                        CASE
			                -- Se a data/hora do contato for anterior a data/hora atual, está ATRASADO
			                WHEN (
			                    CASE
			                        WHEN ce.data_novo_contato IS NULL THEN ce.data_evento
			                        ELSE ce.data_novo_contato
			                    END
			                ) < SYSDATE THEN 'ATRASADO'
			                -- Se a data do contato (ignorando a hora) for maior que a data de hoje, é Futuro
			                WHEN TRUNC(
			                    CASE
			                        WHEN ce.data_novo_contato IS NULL THEN ce.data_evento
			                        ELSE ce.data_novo_contato
			                    END
			                ) > TRUNC(SYSDATE) THEN 'FUTURO'
			                -- Caso contrário, é para hoje (de agora até o fim do dia)
			                ELSE 'TRABALHANDO'
			            END AS status_atendimento
                    FROM
                        CRM_EVENTOS ce
                    LEFT JOIN EMPRESAS_USUARIOS eu ON eu.nome = ce.RESPONSAVEL_PELO_EVENTO
                    LEFT JOIN CRM_ANDAMENTO ca ON ca.COD_ANDAMENTO = ce.COD_ANDAMENTO
                    LEFT JOIN MIDIA m ON m.COD_MIDIA = ce.COD_MIDIA 
                    LEFT JOIN clientes c ON ce.COD_CLIENTE = c.COD_CLIENTE
                    LEFT JOIN CRM_EVENTOS_TIPO cet ON cet.COD_TIPO_EVENTO = ce.COD_TIPO_EVENTO
                    LEFT JOIN CRM_DESCARTES cd on cd.COD_DESCARTE = ce.COD_DESCARTE
                    LEFT JOIN CRM_MOTIVO_PERDAS cmp ON cmp.cod_motivo_perda = ce.cod_motivo_perda
                    LEFT JOIN produtos_modelos pm ON pm.COD_PRODUTO = ce.COD_PRODUTO AND pm.COD_MODELO = ce.COD_MODELO 
                    WHERE
                        1 = 1
                        --AND ce.COD_TIPO_EVENTO IN (785)
                        {filter_responsavel}
        """
        query += f" AND ce.COD_EMPRESA = {cod_empresa} AND ce.COD_EVENTO = {cod_evento} "
        cur_oracle.execute(query)
        row = cur_oracle.fetchall()
        
        if len(row) == 0:
            return jsonify({'status': 'error', 'message': 'Evento não encontrado ou você não tem permissão para acessá-lo'}), 404
        row = row[0]
        if row[1]:  # data_criacao
            try:
                data_criacao_obj = datetime.strptime(row[1], '%Y-%m-%d %H:%M:%S')
                data_criacao_iso = data_criacao_obj.isoformat()
            except:
                data_criacao_iso = row[1]  # fallback para string original
        
        if row[2]:  # data_contato
            try:
                data_contato_obj = datetime.strptime(row[2], '%Y-%m-%d %H:%M:%S')
                data_contato_iso = data_contato_obj.isoformat()
            except:
                data_contato_iso = row[2]  # fallback para string original
        if row[26]:  # data_agendada
            try:
                data_agendada_obj = datetime.strptime(row[26], '%Y-%m-%d %H:%M:%S')
                data_agendada_iso = data_agendada_obj.isoformat()
            except:
                data_agendada_iso = row[26]  # fallback para string original
        if row[27]:  # data_visita
            try:
                data_visita_obj = datetime.strptime(row[27], '%Y-%m-%d %H:%M:%S')
                data_visita_iso = data_visita_obj.isoformat()
            except:
                data_visita_iso = row[27]  # fallback para string original
        obs_memo_processado = processar_obs_memo(row[14])

        retorno = {  
            'status': row[0],
            'data_criacao': data_criacao_iso,
            'data_contato': data_contato_iso,
            'cod_evento': row[3],
            'cod_empresa': row[4],
            'desc_tipo_evento': row[5],
            'andamento': row[6],
            'cod_cliente': row[7],
            'nome_cliente': row[8],
            'tel_cel': row[9],
            'fone_cliente_avulso': row[10],
            'email_cliente_avulso': row[11],
            'email_nfe': row[12],
            'termometro': row[13],
            'obs_memo': row[14],
            'motivo_perda': row[15],
            'descricao_descarte': row[16],
            'responsavel_pelo_evento': row[17],
            'responsavel_nome_completo': row[18],
            'descricao_modelo': row[19],
            'tel_residencial': row[20],
            'tel_comercial': row[21],
            'tel_fax': row[22],
            'tel_whatsapp': row[23],
            'cod_midia': row[24],
            'desc_midia': row[25],
            'data_agendada': data_agendada_iso if row[26] else None,
            'data_visita': data_visita_iso if row[27] else None,
            'status_atendimento': row[28]
        }
        query = f"""
            SELECT
                ca.COD_ACAO,
                ca.RESPONSAVEL,
                ca.quem_criou,
                ca."DATA",
                cat.desc_tipo_acao,
                ca.OBSERVACAO,
                ca.STATUS
            FROM
                CRM_ACOES ca
            LEFT JOIN crm_acoes_tipo cat ON
                1 = 1
                AND cat.tipo_acao = ca.TIPO_ACAO
            WHERE 1=1
                AND ca.COD_EMPRESA = {cod_empresa}
                AND ca.COD_EVENTO = {cod_evento}
            ORDER BY
                DATA desc
        """
        cur_oracle.execute(query)
        rows = cur_oracle.fetchall()
        retorno['acoes'] = []
        for row in rows:
            if row[3]:  # data
                try:
                    data_obj = datetime.strptime(row[3], '%Y-%m-%d %H:%M:%S')
                    data_iso = data_obj.isoformat()
                except:
                    data_iso = row[3]  # fallback para string original
            retorno['acoes'].append({
                'cod_acao': row[0],
                'responsavel': row[1],
                'quem_criou': row[2],
                'data': data_iso,
                'desc_tipo_acao': row[4],
                'observacao': row[5],
                'status': row[6]
            })
        cur_oracle.close()
        conn_oracle.close()
        return jsonify(retorno), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
@crm_bp.route('/api/crm/eventos_showroom/<int:id_evento>', methods=['DELETE'])
@token_required
def delete_crm_eventos_showroom(id_evento):
    try:
        retorno = {}
        token_data = request.token_data
        email = token_data.get('email').strip().lower()
        cod_empresa = str(id_evento)[:2]
        if cod_empresa not in ['11', '33']:
            return jsonify({'status': 'error', 'message': 'ID do evento inválido'}), 400
        cod_evento = str(id_evento)[2:]
        if not cod_evento.isdigit():
            return jsonify({'status': 'error', 'message': 'ID do evento inválido'}), 400
        cod_evento = int(cod_evento)
        
        if email != 'pablo.ti@caiuas.com.br':
            return jsonify({'status': 'error', 'message': 'Apenas o usuário pablo.ti@caiuas.com.br pode deletar eventos'}), 403
        
        conn_oracle, cur_oracle = oracle()
        
        query = f"""
            select count(*)
            from crm_eventos ce
            where 1=1
                and ce.cod_empresa = {cod_empresa}
                and ce.cod_evento = {cod_evento}
        """
        cur_oracle.execute(query)
        row = cur_oracle.fetchone()

        if row[0] == 0:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'Evento não encontrado'}), 404
        
        query = f"""
            update OS_AGENDA_SERVICOS_CANC 
            set CRM_COD_EVENTO = null,
            CRM_COD_EMPRESA = null
            where CRM_COD_EMPRESA = {cod_empresa}
            and CRM_COD_EVENTO = {cod_evento}
        """
        cur_oracle.execute(query)
        query = f"""
            update OS_AGENDA_SERVICOS_CANC 
            set CRM_COD_EVENTO = null,
            CRM_COD_EMPRESA = null
            where COD_EMPRESA = {cod_empresa}
            and CRM_COD_EVENTO = {cod_evento}
        """
        cur_oracle.execute(query)

        query = f"""
            update OS_AGENDA_CANC 
            set CRM_COD_EVENTO = null,
            CRM_COD_EMPRESA = null
            where CRM_COD_EMPRESA = {cod_empresa}
            and CRM_COD_EVENTO = {cod_evento}
        """
        cur_oracle.execute(query)
        query = f"""
            update OS_AGENDA_CANC 
            set CRM_COD_EVENTO = null,
            CRM_COD_EMPRESA = null
            where COD_EMPRESA = {cod_empresa}
            and CRM_COD_EVENTO = {cod_evento}
        """
        cur_oracle.execute(query)

        query = f"""
            update OS_AGENDA_SERVICOS 
            set CRM_COD_EVENTO = null,
            CRM_COD_EMPRESA = null
            where CRM_COD_EMPRESA = {cod_empresa}
            and CRM_COD_EVENTO = {cod_evento}
        """
        cur_oracle.execute(query)
        query = f"""
            update OS_AGENDA_SERVICOS 
            set CRM_COD_EVENTO = null,
            CRM_COD_EMPRESA = null
            where COD_EMPRESA = {cod_empresa}
            and CRM_COD_EVENTO = {cod_evento}
        """
        cur_oracle.execute(query)

        query = f"""
            update OS_AGENDA 
            set CRM_COD_EVENTO = null,
            CRM_COD_EMPRESA = null
            where CRM_COD_EMPRESA = {cod_empresa}
            and CRM_COD_EVENTO = {cod_evento}
        """
        cur_oracle.execute(query)
        query = f"""
            update OS_AGENDA 
            set CRM_COD_EVENTO = null,
            CRM_COD_EMPRESA = null
            where COD_EMPRESA = {cod_empresa}
            and CRM_COD_EVENTO = {cod_evento}
        """
        cur_oracle.execute(query)

        query = f"""
            update ORC_MAPA 
            set COD_EVENTO = null
            where COD_EMPRESA = {cod_empresa}
            and COD_EVENTO = {cod_evento}
        """
        cur_oracle.execute(query)

        query = f"""
            delete from CRM_EVENTO_LOG
            where COD_EMPRESA = {cod_empresa}
            and COD_EVENTO = {cod_evento}
        """
        cur_oracle.execute(query)

        query = f"""
            delete from CRM_RESPOSTAS
            where COD_EMPRESA = {cod_empresa}
            and COD_EVENTO = {cod_evento}
        """
        cur_oracle.execute(query)

        query = f"""
            delete from CRM_ACOES
            where COD_EMPRESA = {cod_empresa}
            and COD_EVENTO = {cod_evento}
        """
        cur_oracle.execute(query)

        query = f"""
            delete from CRM_EVENTOS
            where COD_EMPRESA = {cod_empresa}
            and COD_EVENTO = {cod_evento}
        """
        cur_oracle.execute(query)

        conn_oracle.commit()
        cur_oracle.close()
        conn_oracle.close()
        
        retorno['status'] = 'success'
        retorno['message'] = f'Evento {cod_empresa}{cod_evento} deletado com sucesso'
        return jsonify(retorno), 200
    except Exception as e:
        try:
            conn_oracle.rollback()
            cur_oracle.close()
            conn_oracle.close()
        except:
            pass
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
@crm_bp.route('/api/crm/eventos_showroom/param_create', methods=['GET'])
@token_required
def get_param_create_crm_eventos_showroom():
    try:
        retorno = {}
        token_data = request.token_data
        email = token_data.get('email').strip().lower()
        conn_oracle, cur_oracle = oracle()

        # checar acesso
        query = f"""
            SELECT saf.COD_ACESSO 
            FROM empresas_usuarios eu
            LEFT JOIN SISTEMA_ACESSO_FUNCAO saf ON 1=1
                AND saf.COD_FUNCAO = eu.COD_FUNCAO 
            WHERE 1=1
                AND eu.DEMITIDO <> 'S'
                AND lower(eu.EMAIl) = '{email}'
                AND saf.COD_ACESSO = '80307'
            GROUP BY saf.COD_ACESSO
        """
        cur_oracle.execute(query)
        rows = cur_oracle.fetchall()
        if len(rows) == 0:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'Você não tem permissão para criar eventos showroom - 80307'}), 403
        
         # pegar andamentos

        query = f"""
            SELECT COD_ANDAMENTO, ANDAMENTO
            FROM CRM_ANDAMENTO ca WHERE ativo = 'S'
        """
        cur_oracle.execute(query)
        andamentos = cur_oracle.fetchall()
        if len(andamentos) == 0:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'Não tem andamentos cadastrados'}), 400
        retorno['andamentos'] = []
        for row in andamentos:
            retorno['andamentos'].append({
                'cod_andamento': row[0],
                'andamento': row[1]
            })
        
        query = f"""
            SELECT e.nome, eu.nome, eu.NOME_COMPLETO, eu.EMAIL 
            FROM EMPRESAS_USUARIOS eu
            LEFT JOIN empresas e ON 1=1
                AND e.COD_EMPRESA = eu.COD_EMPRESA 
            WHERE DEMITIDO <> 'S'
            AND COD_FUNCAO <> 2
            AND eu.email IS NOT NULL
        """
        cur_oracle.execute(query)
        usuarios = cur_oracle.fetchall()
        if len(usuarios) == 0:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'Não tem usuários cadastrados'}), 400
        retorno['usuarios'] = []
        for row in usuarios:
            retorno['usuarios'].append({
                'empresa': row[0],
                'nome_usuario': row[1],
                'nome_completo': row[2],
                'email': row[3]
            })
        
        query = f"""
                SELECT * FROM CRM_EVENTOS_TIPO cet 
                WHERE cod_area IN (124, 146)
                AND ativo = 'S'
                AND COD_QUESTIONARIO IS null
        """
        cur_oracle.execute(query)
        tipos_evento = cur_oracle.fetchall()
        if len(tipos_evento) == 0:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'Não tem tipos de evento cadastrados'}), 400
        retorno['tipos_evento'] = []
        for row in tipos_evento:
            retorno['tipos_evento'].append({
                'cod_tipo_evento': row[0],
                'desc_tipo_evento': row[1],
                'cod_grupo': row[2],
                'cod_area': row[3],
                'requer_produto': row[4],
                'requer_modelo': row[5],
                'ativo': row[6]
            })
        query = f"""
            SELECT pm.DESCRICAO_MODELO, pm.COD_PRODUTO, pm.COD_MODELO 
            FROM PRODUTOS_MODELOS pm
            WHERE 1=1
                --AND pm.ATIVO = 'S'
                and pm.internet = 'S'
            order by pm.descricao_modelo
        """
        cur_oracle.execute(query)
        produtos_modelos = cur_oracle.fetchall()
        if len(produtos_modelos) == 0:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'Não tem produtos/modelos cadastrados'}), 400
        retorno['produtos_modelos'] = []
        for row in produtos_modelos:
            retorno['produtos_modelos'].append({
                'descricao_modelo': row[0],
                'cod_produto': row[1],
                'cod_modelo': row[2]
            })
        
        query = f"""
            SELECT COD_MIDIA, DESCRICAO 
            FROM MIDIA m 
            WHERE ativo = 'S'
        """
        cur_oracle.execute(query)
        midias = cur_oracle.fetchall()
        if len(midias) == 0:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'Não tem mídias cadastradas'}), 400
        retorno['midias'] = []
        for row in midias:
            retorno['midias'].append({
                'cod_midia': row[0],
                'descricao': row[1]
            })

        cur_oracle.close()
        conn_oracle.close()
        
        return jsonify(retorno), 200
    except Exception as e:
        try:
            cur_oracle.close()
            conn_oracle.close()
        except:
            pass
        return jsonify({'status': 'error', 'message': str(e)}), 500

@crm_bp.route('/api/crm/eventos_showroom', methods=['POST'])
@token_required
def create_crm_eventos_showroom():
    try:
        token_data = request.token_data
        email = token_data.get('email').strip().lower()
        data = request.get_json()
        cod_tipo_evento = data.get('cod_tipo_evento', None)
        cod_andamento = data.get('cod_andamento', None)
        responsavel_pelo_evento = data.get('responsavel', None)
        cod_cliente = data.get('cod_cliente', None)
        nome_cliente_avulso = data.get('nome_cliente', None)
        fone_cliente_avulso = data.get('telefone', None)
        email_cliente_avulso = data.get('email', None)
        cod_produto = data.get('cod_produto', None)
        cod_modelo = data.get('cod_modelo', None)
        cod_midia = data.get('cod_midia', None)
        obsercacao = data.get('observacao', None)
        cod_modelo = int(cod_modelo) if cod_modelo and str(cod_modelo).isdigit() else None

        conn_oracle, cur_oracle = oracle()
        if not cod_tipo_evento:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'Tipo do evento é obrigatório'}), 400
        if not cod_andamento:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'Andamento é obrigatório'}), 400
        if not responsavel_pelo_evento:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'Responsável pelo evento é obrigatório'}), 400
        if not cod_cliente and not nome_cliente_avulso:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'Cliente ou nome do cliente avulso é obrigatório'}), 400
        if not cod_midia:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'Mídia é obrigatória'}), 400
        if not obsercacao:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'Observação é obrigatória'}), 400

        # checar acesso
        query = f"""
            SELECT saf.COD_ACESSO 
            FROM empresas_usuarios eu
            LEFT JOIN SISTEMA_ACESSO_FUNCAO saf ON 1=1
                AND saf.COD_FUNCAO = eu.COD_FUNCAO 
            WHERE 1=1
                AND eu.DEMITIDO <> 'S'
                AND lower(eu.EMAIl) = '{email}'
                AND saf.COD_ACESSO = '80307'
            GROUP BY saf.COD_ACESSO
        """
        cur_oracle.execute(query)
        rows = cur_oracle.fetchall()
        if len(rows) == 0:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'Você não tem permissão para criar eventos showroom - 80307'}), 403
        
        query = f"""
            SELECT cod_empresa,eu.nome 
            FROM empresas_usuarios eu
            LEFT JOIN SISTEMA_ACESSO_FUNCAO saf ON 1=1
                AND saf.COD_FUNCAO = eu.COD_FUNCAO 
            WHERE 1=1
                AND eu.DEMITIDO <> 'S'
                AND lower(eu.EMAIl) = '{email}'
            GROUP BY eu.COD_EMPRESA, eu.nome
            ORDER BY eu.cod_empresa
        """
        cur_oracle.execute(query)
        rows = cur_oracle.fetchall()
        criou_o_evento = rows[0][1]
        if cod_modelo:
            query = f"""
                SELECT COD_PRODUTO FROM PRODUTOS_MODELOS pm WHERE COD_MODELO = {cod_modelo}
            """
            cur_oracle.execute(query)
            rows = cur_oracle.fetchall()
            if len(rows) == 0:
                cur_oracle.close()
                conn_oracle.close()
                return jsonify({'status': 'error', 'message': 'Modelo não encontrado'}), 400
            cod_produto = rows[0][0]

        query = f"""
            insert into crm_eventos(COD_EMPRESA,
                                    COD_EVENTO,
                                    COD_TIPO_EVENTO,
                                    COD_PRIORIDADE,
                                    NOME_CLIENTE_AVULSO ,
                                    FONE_CLIENTE_AVULSO,
                                    cod_midia,
                                    data_criacao ,
                                    cod_cliente_honda ,
                                    DESC_EVENTO,
                                    CRIOU_O_EVENTO,
                                    DATA_EVENTO,
                                    OBS_memo,
                                    COD_ANDAMENTO,
                                    COD_CLIENTE,
                                    STATUS,
                                    RESPONSAVEL_PELO_EVENTO,
                                    TIPO_ATENDIMENTO,
                                    COD_PRODUTO,
                                    COD_MODELO,
                                    EMAIL_CLIENTE_AVULSO)
                            VALUES(11,
                            seq_crm_COD_EVENTO.nextval,
                            {cod_tipo_evento},
                            2,
                            '{nome_cliente_avulso}' ,
                            '{fone_cliente_avulso}',
                            {cod_midia},
                            SYSDATE,
                            seq_cod_cliente_honda.nextval,
                            {'\'Evento criado via API\'' if not obsercacao else f"'{obsercacao[:200]}'"},
                            '{criou_o_evento}',
                            SYSDATE,
                            '{obsercacao}',
                            {cod_andamento},
                            {cod_cliente if cod_cliente else 1},
                            'P',
                            '{responsavel_pelo_evento}',
                            null,
                            {cod_produto if cod_produto else 'null'},
                            {cod_modelo if cod_modelo else 'null'},
                            '{email_cliente_avulso}')
        """
        cur_oracle.execute(query)
        conn_oracle.commit()
        cur_oracle.close()
        conn_oracle.close()
        retorno = {}
        retorno['message'] = 'Evento criado com sucesso'
        return jsonify(retorno), 201

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
@crm_bp.route('/api/crm/eventos_showroom/remarca_contato/<int:id_evento>', methods=['POST'])
@token_required
def crm_eventos_showroom_remarca_contato(id_evento):
    try:
        token_data = request.token_data
        email = token_data.get('email').strip().lower()
        data = request.get_json()
        nova_data_hora = data.get('nova_data_hora', None)
        if not nova_data_hora:
            return jsonify({'status': 'error', 'message': 'Nova data/hora é obrigatória'}), 400
        try:
            nova_data_hora_obj = datetime.fromisoformat(nova_data_hora)
            nova_data_hora_str = nova_data_hora_obj.strftime('%Y-%m-%d %H:%M:%S')
        except:
            return jsonify({'status': 'error', 'message': 'Formato da nova data/hora inválido. Use ISO 8601'}), 400

        cod_empresa = str(id_evento)[:2]
        if cod_empresa not in ['11', '33']:
            return jsonify({'status': 'error', 'message': 'ID do evento inválido'}), 400
        cod_evento = str(id_evento)[2:]
        if not cod_evento.isdigit():
            return jsonify({'status': 'error', 'message': 'ID do evento inválido'}), 400
        cod_evento = int(cod_evento)

        conn_oracle, cur_oracle = oracle()
        
        query = f"""
            SELECT saf.COD_ACESSO 
            FROM empresas_usuarios eu
            LEFT JOIN SISTEMA_ACESSO_FUNCAO saf ON 1=1
                AND saf.COD_FUNCAO = eu.COD_FUNCAO 
            WHERE 1=1
                AND eu.DEMITIDO <> 'S'
                AND lower(eu.EMAIl) = '{email}'
                AND saf.COD_ACESSO = '80320'
            GROUP BY saf.COD_ACESSO
        """
        conn_oracle, cur_oracle = oracle()
        cur_oracle.execute(query)
        rows = cur_oracle.fetchall()
        filter_responsavel = ''
        if len(rows) == 0:
            filter_responsavel = f" AND lower(eu.EMAIl) = '{email}' "
        
        query = f"""
            select data_criacao
            from crm_eventos ce
            where 1=1
                and ce.cod_empresa = {cod_empresa}
                and ce.cod_evento = {cod_evento}
                {filter_responsavel}
        """
        cur_oracle.execute(query)
        row = cur_oracle.fetchone()

        if len(row) == 0:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'Evento não encontrado'}), 404
        
        if isinstance(row[0], datetime):
            data_criacao_str = row[0].strftime('%Y-%m-%d %H:%M:%S')
        else:
            data_criacao_str = str(row[0])

        if nova_data_hora_str < data_criacao_str:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'A nova data/hora do contato não pode ser anterior à data/hora de criação do evento'}), 400
        
        query = f"""
            SELECT cod_empresa,eu.nome 
            FROM empresas_usuarios eu
            LEFT JOIN SISTEMA_ACESSO_FUNCAO saf ON 1=1
                AND saf.COD_FUNCAO = eu.COD_FUNCAO 
            WHERE 1=1
                AND eu.DEMITIDO <> 'S'
                AND lower(eu.EMAIl) = '{email}'
            GROUP BY eu.COD_EMPRESA, eu.nome
            ORDER BY eu.cod_empresa
        """
        cur_oracle.execute(query)
        rows = cur_oracle.fetchall()
        quem_remarcou = rows[0][1]
        
        query = f"""
            update crm_eventos
            set data_novo_contato = TO_DATE('{nova_data_hora_str}', 'YYYY-MM-DD HH24:MI:SS'),
            quem_remarcou = '{quem_remarcou}'
            where cod_empresa = {cod_empresa}
            and cod_evento = {cod_evento}
        """
        cur_oracle.execute(query)
        
        query = f"""
            insert into crm_acoes
            (cod_empresa,cod_evento, responsavel, tipo_acao, data, observacao, status, cod_acao, quem_criou, data_novo_contato)
            values (
                {cod_empresa},
                {cod_evento},
                '{quem_remarcou}',
                13,
                SYSDATE,
                'Contato remarcado para {nova_data_hora_str} por {quem_remarcou}',
                'P',
                seq_crm_COD_ACAO.nextval,
                '{quem_remarcou}',
                TO_DATE('{nova_data_hora_str}', 'YYYY-MM-DD HH24:MI:SS')
            )
        """
        cur_oracle.execute(query)
        # return query
        
        
        conn_oracle.commit()
        cur_oracle.close()
        conn_oracle.close()
        
        retorno = {}
        retorno['status'] = 'success'
        retorno['message'] = f'Contato do evento {cod_empresa}{cod_evento} remarcado para {nova_data_hora_str}'
        return jsonify(retorno), 200
    except Exception as e:
        try:
            conn_oracle.rollback()
            cur_oracle.close()
            conn_oracle.close()
        except:
            pass
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
@crm_bp.route('/api/crm/eventos_showroom/update_observacao/<int:id_evento>', methods=['POST'])
@token_required
def crm_eventos_showroom_update_observacao(id_evento):
    try:
        token_data = request.token_data
        email = token_data.get('email').strip().lower()
        data = request.get_json()
        # nova_data_hora = data.get('nova_data_hora', None)
        observacao = data.get('observacao', None)
        if not observacao or observacao.strip() == '':
            obs_value = 'NULL'
        else:
            # Escapar aspas simples duplicando-as
            observacao_escaped = observacao.replace("'", "''")
            obs_value = f"'{observacao_escaped}'"
        # if not nova_data_hora:
        #     return jsonify({'status': 'error', 'message': 'Nova data/hora é obrigatória'}), 400
        # try:
        #     nova_data_hora_obj = datetime.fromisoformat(nova_data_hora)
        #     nova_data_hora_str = nova_data_hora_obj.strftime('%Y-%m-%d %H:%M:%S')
        # except:
        #     return jsonify({'status': 'error', 'message': 'Formato da nova data/hora inválido. Use ISO 8601'}), 400

        cod_empresa = str(id_evento)[:2]
        if cod_empresa not in ['11', '33']:
            return jsonify({'status': 'error', 'message': 'ID do evento inválido'}), 400
        cod_evento = str(id_evento)[2:]
        if not cod_evento.isdigit():
            return jsonify({'status': 'error', 'message': 'ID do evento inválido'}), 400
        cod_evento = int(cod_evento)

        conn_oracle, cur_oracle = oracle()
        
        query = f"""
            SELECT saf.COD_ACESSO 
            FROM empresas_usuarios eu
            LEFT JOIN SISTEMA_ACESSO_FUNCAO saf ON 1=1
                AND saf.COD_FUNCAO = eu.COD_FUNCAO 
            WHERE 1=1
                AND eu.DEMITIDO <> 'S'
                AND lower(eu.EMAIl) = '{email}'
                AND saf.COD_ACESSO = '80320'
            GROUP BY saf.COD_ACESSO
        """
        conn_oracle, cur_oracle = oracle()
        cur_oracle.execute(query)
        rows = cur_oracle.fetchall()
        filter_responsavel = ''
        if len(rows) == 0:
            filter_responsavel = f" AND lower(eu.EMAIl) = '{email}' "
        
        query = f"""
            select data_criacao
            from crm_eventos ce
            where 1=1
                and ce.cod_empresa = {cod_empresa}
                and ce.cod_evento = {cod_evento}
                {filter_responsavel}
        """
        cur_oracle.execute(query)
        row = cur_oracle.fetchone()

        if len(row) == 0:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'Evento não encontrado'}), 404
        
        # if isinstance(row[0], datetime):
        #     data_criacao_str = row[0].strftime('%Y-%m-%d %H:%M:%S')
        # else:
        #     data_criacao_str = str(row[0])

        # if nova_data_hora_str < data_criacao_str:
        #     cur_oracle.close()
        #     conn_oracle.close()
        #     return jsonify({'status': 'error', 'message': 'A nova data/hora do contato não pode ser anterior à data/hora de criação do evento'}), 400
        
        query = f"""
            SELECT cod_empresa,eu.nome 
            FROM empresas_usuarios eu
            LEFT JOIN SISTEMA_ACESSO_FUNCAO saf ON 1=1
                AND saf.COD_FUNCAO = eu.COD_FUNCAO 
            WHERE 1=1
                AND eu.DEMITIDO <> 'S'
                AND lower(eu.EMAIl) = '{email}'
            GROUP BY eu.COD_EMPRESA, eu.nome
            ORDER BY eu.cod_empresa
        """
        cur_oracle.execute(query)
        rows = cur_oracle.fetchall()
        quem_remarcou = rows[0][1]
        
        query = f"""
            update crm_eventos
            set OBS_memo = {obs_value}
            where cod_empresa = {cod_empresa}
            and cod_evento = {cod_evento}
        """
        # query = query.replace("''", "'")
        # return query
        cur_oracle.execute(query)
        
        query = f"""
            insert into crm_acoes
            (cod_empresa,cod_evento, responsavel, tipo_acao, data, observacao, status, cod_acao, quem_criou)
            values (
                {cod_empresa},
                {cod_evento},
                '{quem_remarcou}',
                4,
                SYSDATE,
                'Observação atualizada por: {quem_remarcou}',
                'P',
                seq_crm_COD_ACAO.nextval,
                '{quem_remarcou}'
            )
        """
        cur_oracle.execute(query)

        conn_oracle.commit()
        cur_oracle.close()
        conn_oracle.close()

        retorno = {}
        retorno['status'] = 'success'
        retorno['message'] = f'Observação do evento {cod_empresa}{cod_evento} atualizada com sucesso'
        return jsonify(retorno), 200
    except Exception as e:
        try:
            conn_oracle.rollback()
            cur_oracle.close()
            conn_oracle.close()
        except:
            pass
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
@crm_bp.route('/api/crm/eventos_showroom/agenda_visita/<int:id_evento>', methods=['POST'])
@token_required
def crm_eventos_showroom_agenda_visita(id_evento):
    try:
        token_data = request.token_data
        email = token_data.get('email').strip().lower()
        data = request.get_json()
        data_agendada = data.get('data_agendada', None)
        data_visita = data.get('data_visita', None)
        
        # Validar ID do evento
        cod_empresa = str(id_evento)[:2]
        if cod_empresa not in ['11', '33']:
            return jsonify({'status': 'error', 'message': 'ID do evento inválido'}), 400
        cod_evento = str(id_evento)[2:]
        if not cod_evento.isdigit():
            return jsonify({'status': 'error', 'message': 'ID do evento inválido'}), 400
        cod_evento = int(cod_evento)

        conn_oracle, cur_oracle = oracle()
        
        # Verificar permissões
        query = f"""
            SELECT saf.COD_ACESSO FROM empresas_usuarios eu
            LEFT JOIN SISTEMA_ACESSO_FUNCAO saf ON saf.COD_FUNCAO = eu.COD_FUNCAO 
            WHERE eu.DEMITIDO <> 'S' AND lower(eu.EMAIl) = '{email}' AND saf.COD_ACESSO = '80320'
        """
        cur_oracle.execute(query)
        has_access = len(cur_oracle.fetchall()) > 0
        filter_responsavel = '' if has_access else f" AND lower(eu.EMAIl) = '{email}' "
        
        # Buscar evento
        query = f"""
            SELECT data_criacao, data_agendada, data_visita FROM crm_eventos ce
            WHERE ce.cod_empresa = {cod_empresa} AND ce.cod_evento = {cod_evento} {filter_responsavel}
        """
        cur_oracle.execute(query)
        row = cur_oracle.fetchone()
        if not row:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'Evento não encontrado'}), 404
        
        data_criacao, data_agendada_atual, data_visita_atual = row
        
        # Buscar usuário
        query = f"""
            SELECT nome FROM (
                SELECT eu.nome FROM empresas_usuarios eu
                WHERE eu.DEMITIDO <> 'S' AND lower(eu.EMAIl) = '{email}'
                ORDER BY eu.cod_empresa
            ) WHERE ROWNUM = 1
        """
        cur_oracle.execute(query)
        quem_alterou = cur_oracle.fetchone()[0]
        
        observacoes = []
        updates = [f"quem_remarcou = '{quem_alterou}'"]
        
        # Aplicar regras - corrigido para evitar duplicação
        if 'data_agendada' in data and data_agendada is None:
            # data_agendada = null -> remove ambas
            updates.extend(["data_agendada = NULL", "data_visita = NULL"])
            observacoes.append("Removido agendamento de visita")
            
        elif data_agendada:
            # Validar formato da data_agendada
            try:
                data_agendada_obj = datetime.fromisoformat(data_agendada)
                data_agendada_str = data_agendada_obj.strftime('%Y-%m-%d %H:%M:%S')
            except:
                cur_oracle.close()
                conn_oracle.close()
                return jsonify({'status': 'error', 'message': 'Formato da data_agendada inválido'}), 400
            
            # Verificar se não é anterior à criação
            data_criacao_str = data_criacao.strftime('%Y-%m-%d %H:%M:%S') if isinstance(data_criacao, datetime) else str(data_criacao)
            if data_agendada_str < data_criacao_str:
                cur_oracle.close()
                conn_oracle.close()
                return jsonify({'status': 'error', 'message': 'Data agendada não pode ser anterior à criação do evento'}), 400
            
            updates.append(f"data_agendada = TO_DATE('{data_agendada_str}', 'YYYY-MM-DD HH24:MI:SS')")
            observacoes.append(f"Agendamento marcado para dia {data_agendada_str}")
            
            # Processar data_visita apenas se data_agendada não foi removida
            if 'data_visita' in data:
                if data_visita is None:
                    updates.append("data_visita = NULL")
                    # Só adiciona observação se já existia data de visita
                    if data_visita_atual:
                        observacoes.append("Removido data de visita")
                else:
                    # Validar formato da data_visita
                    try:
                        data_visita_obj = datetime.fromisoformat(data_visita)
                        data_visita_str = data_visita_obj.strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        cur_oracle.close()
                        conn_oracle.close()
                        return jsonify({'status': 'error', 'message': 'Formato da data_visita inválido'}), 400
                    
                    # Verificar se data_visita não é menor que data_agendada
                    if data_visita_str < data_agendada_str:
                        cur_oracle.close()
                        conn_oracle.close()
                        return jsonify({'status': 'error', 'message': 'A data_visita não pode ser anterior à data_agendada'}), 400
                    
                    updates.append(f"data_visita = TO_DATE('{data_visita_str}', 'YYYY-MM-DD HH24:MI:SS')")
                    observacoes.append(f"Data de visita alterada para {data_visita_str}")
        
        # Processar data_visita apenas se data_agendada não foi processada
        elif 'data_visita' in data:
            if data_visita is None:
                updates.append("data_visita = NULL")
                # Só adiciona observação se já existia data de visita
                if data_visita_atual:
                    observacoes.append("Removido data de visita")
            else:
                # Verificar se tem data_agendada atual
                if not data_agendada_atual:
                    cur_oracle.close()
                    conn_oracle.close()
                    return jsonify({'status': 'error', 'message': 'Não é possível definir data_visita sem uma data_agendada'}), 400
                
                # Validar formato da data_visita
                try:
                    data_visita_obj = datetime.fromisoformat(data_visita)
                    data_visita_str = data_visita_obj.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    cur_oracle.close()
                    conn_oracle.close()
                    return jsonify({'status': 'error', 'message': 'Formato da data_visita inválido'}), 400
                
                # Verificar se data_visita não é menor que data_agendada
                data_agendada_comparar = data_agendada_atual.strftime('%Y-%m-%d %H:%M:%S') if isinstance(data_agendada_atual, datetime) else str(data_agendada_atual)
                if data_visita_str < data_agendada_comparar:
                    cur_oracle.close()
                    conn_oracle.close()
                    return jsonify({'status': 'error', 'message': 'A data_visita não pode ser anterior à data_agendada'}), 400
                
                updates.append(f"data_visita = TO_DATE('{data_visita_str}', 'YYYY-MM-DD HH24:MI:SS')")
                observacoes.append(f"Data de visita alterada para {data_visita_str}")
        
        if not observacoes:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'Nenhuma alteração solicitada'}), 400
        
        # Atualizar evento
        query = f"""
            UPDATE crm_eventos SET {', '.join(updates)}
            WHERE cod_empresa = {cod_empresa} AND cod_evento = {cod_evento}
        """
        cur_oracle.execute(query)
        
        # Inserir ação
        observacao_final = ' - '.join(observacoes)
        query = f"""
            INSERT INTO crm_acoes (cod_empresa, cod_evento, responsavel, tipo_acao, data, observacao, status, cod_acao, quem_criou)
            VALUES ({cod_empresa}, {cod_evento}, '{quem_alterou}', 12, SYSDATE, '{observacao_final}', 'V', seq_crm_COD_ACAO.nextval, '{quem_alterou}')
        """
        cur_oracle.execute(query)
        
        conn_oracle.commit()
        cur_oracle.close()
        conn_oracle.close()
        
        return jsonify({'status': 'success', 'message': observacao_final}), 200
        
    except Exception as e:
        try:
            conn_oracle.rollback()
            cur_oracle.close()
            conn_oracle.close()
        except:
            pass
        return jsonify({'status': 'error', 'message': str(e)}), 500
  
@crm_bp.route('/api/crm/eventos_showroom/create_acao/<int:id_evento>', methods=['POST'])
@token_required
def crm_eventos_showroom_create_acao(id_evento):
    try:
        token_data = request.token_data
        email = token_data.get('email').strip().lower()
        data = request.get_json()
        tipo_acao = data.get('tipo_acao', None)
        observacao = data.get('observacao', None)
        if not tipo_acao or not str(tipo_acao).isdigit():
            return jsonify({'status': 'error', 'message': 'Tipo de ação é obrigatório'}), 400
        tipo_acao = int(tipo_acao)
        if not observacao or observacao.strip() == '':
            return jsonify({'status': 'error', 'message': 'Observação é obrigatória'}), 400
        # Escapar aspas simples duplicando-as
        observacao_escaped = observacao.replace("'", "''")
        
        cod_empresa = str(id_evento)[:2]
        if cod_empresa not in ['11', '33']:
            return jsonify({'status': 'error', 'message': 'ID do evento inválido'}), 400
        cod_evento = str(id_evento)[2:]
        if not cod_evento.isdigit():
            return jsonify({'status': 'error', 'message': 'ID do evento inválido'}), 400
        cod_evento = int(cod_evento)

        conn_oracle, cur_oracle = oracle()
        
        query = f"""
            SELECT saf.COD_ACESSO 
            FROM empresas_usuarios eu
            LEFT JOIN SISTEMA_ACESSO_FUNCAO saf ON 1=1
                AND saf.COD_FUNCAO = eu.COD_FUNCAO 
            WHERE 1=1
                AND eu.DEMITIDO <> 'S'
                AND lower(eu.EMAIl) = '{email}'
                AND saf.COD_ACESSO = '80320'
            GROUP BY saf.COD_ACESSO
        """
        conn_oracle, cur_oracle = oracle()
        cur_oracle.execute(query)
        rows = cur_oracle.fetchall()
        filter_responsavel = ''
        if len(rows) == 0:
            filter_responsavel = f" AND lower(eu.EMAIl) = '{email}' "
        
        query = f"""
            select data_criacao
            from crm_eventos ce
            where 1=1
                and ce.cod_empresa = {cod_empresa}
                and ce.cod_evento = {cod_evento}
                {filter_responsavel}
        """
        cur_oracle.execute(query)
        rows = cur_oracle.fetchall()
        if len(rows) == 0:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'Evento não encontrado'}), 404
        
        query = f"""
            select count(*) FROM CRM_ACOES_TIPO cat
            where 1=1
                and cat.tipo_acao = {tipo_acao}
        """
        # return query
        cur_oracle.execute(query)
        row = cur_oracle.fetchone()
        if row[0] == 0:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'Tipo de ação inválido'}), 400
        
         # Buscar usuário
         # Buscar usuário
        
        
        query = f"""
            SELECT cod_empresa,eu.nome 
            FROM empresas_usuarios eu
            LEFT JOIN SISTEMA_ACESSO_FUNCAO saf ON 1=1
                AND saf.COD_FUNCAO = eu.COD_FUNCAO 
            WHERE 1=1
                AND eu.DEMITIDO <> 'S'
                AND lower(eu.EMAIl) = '{email}'
            GROUP BY eu.COD_EMPRESA, eu.nome
            ORDER BY eu.cod_empresa
        """
        cur_oracle.execute(query)
        rows = cur_oracle.fetchall()
        quem_criou = rows[0][1]
        query = f"""
            insert into crm_acoes
            (cod_empresa,cod_evento, responsavel, tipo_acao, data, observacao, status, cod_acao, quem_criou)
            values (
                {cod_empresa},
                {cod_evento},
                '{quem_criou}',
                {tipo_acao},
                SYSDATE,
                '{observacao_escaped}',
                'P',
                seq_crm_COD_ACAO.nextval,
                '{quem_criou}'
            )
        """
        # return query
        cur_oracle.execute(query)
        conn_oracle.commit()
        cur_oracle.close()
        conn_oracle.close()
        retorno = {}
        retorno['status'] = 'success'
        retorno['message'] = 'Ação criada com sucesso'
        return jsonify(retorno), 201
    except Exception as e:
        try:
            conn_oracle.rollback()
            cur_oracle.close()
            conn_oracle.close()
        except:
            pass
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
@crm_bp.route('/api/crm/eventos_showroom/muda_cliente/<int:id_evento>', methods=['POST'])
@token_required
def crm_eventos_showroom_muda_cliente(id_evento):
    try:
        token_data = request.token_data
        email = token_data.get('email').strip().lower()
        data = request.get_json()
        cod_cliente = data.get('cod_cliente', None)
        conn_oracle, cur_oracle = oracle()
        
        cod_empresa = str(id_evento)[:2]
        if cod_empresa not in ['11', '33']:
            return jsonify({'status': 'error', 'message': 'ID do evento inválido'}), 400
        cod_evento = str(id_evento)[2:]
        if not cod_evento.isdigit():
            return jsonify({'status': 'error', 'message': 'ID do evento inválido'}), 400
        cod_evento = int(cod_evento)
        
        if not cod_cliente or not str(cod_cliente).isdigit():
            return jsonify({'status': 'error', 'message': 'Código do cliente é obrigatório'}), 400
        
        query = f"""
            SELECT saf.COD_ACESSO 
            FROM empresas_usuarios eu
            LEFT JOIN SISTEMA_ACESSO_FUNCAO saf ON 1=1
                AND saf.COD_FUNCAO = eu.COD_FUNCAO 
            WHERE 1=1
                AND eu.DEMITIDO <> 'S'
                AND lower(eu.EMAIl) = '{email}'
                AND saf.COD_ACESSO = '80320'
            GROUP BY saf.COD_ACESSO
        """
        conn_oracle, cur_oracle = oracle()
        cur_oracle.execute(query)
        rows = cur_oracle.fetchall()
        filter_responsavel = ''
        if len(rows) == 0:
            filter_responsavel = f" AND lower(eu.EMAIl) = '{email}' "
        
        query = f"""
            select data_criacao
            from crm_eventos ce
            where 1=1
                and ce.cod_empresa = {cod_empresa}
                and ce.cod_evento = {cod_evento}
                {filter_responsavel}
        """
        cur_oracle.execute(query)
        rows = cur_oracle.fetchall()
        if len(rows) == 0:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'Evento não encontrado'}), 404
        
        query = f"""
            select count(*) from clientes c
            where 1=1
                and c.cod_cliente = {cod_cliente}
        """
        
        cur_oracle.execute(query)
        row = cur_oracle.fetchone()
        if row[0] == 0:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'Não tem clientes cadastrados'}), 400
        
        query = f"""
            update crm_eventos
            set cod_cliente = {cod_cliente}
            where cod_empresa = {cod_empresa}
            and cod_evento = {cod_evento}
        """
        cur_oracle.execute(query)
        conn_oracle.commit()
        cur_oracle.close()
        conn_oracle.close()
        retorno = {}
        retorno['status'] = 'success'
        retorno['message'] = 'Cliente do evento atualizado com sucesso'
        return jsonify(retorno), 200
    except Exception as e:
        try:
            conn_oracle.rollback()
            cur_oracle.close()
            conn_oracle.close()
        except:
            pass
        return jsonify({'status': 'error', 'message': str(e)}), 500
        
@crm_bp.route('/api/crm/eventos/muda_temperatura/<int:id_evento>', methods=['POST'])
@token_required
def crm_eventos_muda_temperatura(id_evento):
    try:
        token_data = request.token_data
        email = token_data.get('email').strip().lower()
        cod_empresa = str(id_evento)[:2]
        cod_temperatura = request.json.get('cod_temperatura', None)
        if cod_empresa not in ['11', '33']:
            return jsonify({'status': 'error', 'message': 'ID do evento inválido'}), 400
        cod_evento = str(id_evento)[2:]
        if not cod_evento.isdigit():
            return jsonify({'status': 'error', 'message': 'ID do evento inválido'}), 400
        conn_oracle, cur_oracle = oracle()

        query = f"""
            SELECT cod_empresa,eu.nome 
            FROM empresas_usuarios eu
            LEFT JOIN SISTEMA_ACESSO_FUNCAO saf ON 1=1
                AND saf.COD_FUNCAO = eu.COD_FUNCAO 
            WHERE 1=1
                AND eu.DEMITIDO <> 'S'
                AND lower(eu.EMAIl) = '{email.lower()}'
            GROUP BY eu.COD_EMPRESA, eu.nome
            ORDER BY eu.cod_empresa
        """
        cur_oracle.execute(query)
        rows = cur_oracle.fetchall()
        quem_remarcou = rows[0][1]
        # se cod_temperatura tiver fora de 0 a 4  cod_temperatura = 0
        if not isinstance(cod_temperatura, int):
            try:
                cod_temperatura = int(cod_temperatura)
            except:
                cod_temperatura = 0
        if cod_temperatura < 0 or cod_temperatura > 4:
            cod_temperatura = 0
        
        # 0 = Sem classificação, 1 = Frio, 2 = Morno, 3 = Quente, 4 = Cliente
        nome_temperatura = {
            0: 'Sem classificação',
            1: 'Frio',
            2: 'Morno',
            3: 'Quente',
            4: 'Cliente'
            }
        
        # Validar ID do evento
        
        cod_empresa = str(id_evento)[:2]
        if cod_empresa not in ['11', '33']:
            return jsonify({'status': 'error', 'message': 'ID do evento inválido'}), 400
        cod_evento = str(id_evento)[2:]
        if not cod_evento.isdigit():
            return jsonify({'status': 'error', 'message': 'ID do evento inválido'}), 400
        cod_evento = int(cod_evento)
        
        # if not cod_temperatura or not str(cod_temperatura).isdigit():
        #     return jsonify({'status': 'error', 'message': 'Código da temperatura é obrigatório'}), 400
        cod_temperatura = int(cod_temperatura)
        
        query = f"""
            SELECT cod_empresa,eu.nome 
            FROM empresas_usuarios eu
            LEFT JOIN SISTEMA_ACESSO_FUNCAO saf ON 1=1
                AND saf.COD_FUNCAO = eu.COD_FUNCAO 
            WHERE 1=1
                AND eu.DEMITIDO <> 'S'
                AND lower(eu.EMAIl) = '{email}'
            GROUP BY eu.COD_EMPRESA, eu.nome
            ORDER BY eu.cod_empresa
        """
        conn_oracle, cur_oracle = oracle()
        cur_oracle.execute(query)
        rows = cur_oracle.fetchall()
        quem_alterou = rows[0][1]
        filter_responsavel = ''
        if len(rows) == 0:
            filter_responsavel = f" AND lower(eu.EMAIl) = '{email}' "
        
        query = f"""
            select data_criacao
            from crm_eventos ce
            where 1=1
                and ce.cod_empresa = {cod_empresa}
                and ce.cod_evento = {cod_evento}
                {filter_responsavel}
        """
        cur_oracle.execute(query)
        rows = cur_oracle.fetchall()
        if len(rows) == 0:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'Evento não encontrado'}), 404
        
        query = f"""
            update crm_eventos
            set termometro = {cod_temperatura}
            where cod_empresa = {cod_empresa}
            and cod_evento = {cod_evento}
        """
        cur_oracle.execute(query)
        query = f"""
            insert into crm_acoes
            (cod_empresa,cod_evento, responsavel, tipo_acao, data, observacao, status, cod_acao, quem_criou)
            values (
                {cod_empresa},
                {cod_evento},
                '{quem_alterou}',
                5,
                SYSDATE,
                'Temperatura alterada para: {nome_temperatura[cod_temperatura]}',
                'P',
                seq_crm_COD_ACAO.nextval,
                '{quem_alterou}'
            )
        """
        cur_oracle.execute(query)
        conn_oracle.commit()
        cur_oracle.close()
        conn_oracle.close()
        retorno = {}
        retorno['status'] = 'success'
        retorno['message'] = 'Temperatura do evento atualizada com sucesso'
        return jsonify(retorno), 200
    except Exception as e:
        try:
            conn_oracle.rollback()
            cur_oracle.close()
            conn_oracle.close()
        except:
            pass
        return jsonify({'status': 'error', 'message': str(e)}), 500

@crm_bp.route('/api/crm/eventos_showroom/muda_modelo_veiculo/<int:id_evento>', methods=['POST'])
@token_required
def crm_eventos_showroom_muda_modelo_veiculo(id_evento):
    try:
        token_data = request.token_data
        email = token_data.get('email').strip().lower()
        cod_empresa = str(id_evento)[:2]
        
        data = request.get_json()
        cod_produto = data.get('cod_produto', None)
        cod_modelo = data.get('cod_modelo', None)
        
        if not cod_produto or not str(cod_produto).isdigit():
            return jsonify({'status': 'error', 'message': 'Código do produto é obrigatório'}), 400
        if not cod_modelo or not str(cod_modelo).isdigit():
            return jsonify({'status': 'error', 'message': 'Código do modelo é obrigatório'}), 400
        
        if cod_empresa not in ['11', '33']:
            return jsonify({'status': 'error', 'message': 'ID do evento inválido'}), 400
        cod_evento = str(id_evento)[2:]
        if not cod_evento.isdigit():
            return jsonify({'status': 'error', 'message': 'ID do evento inválido'}), 400
        conn_oracle, cur_oracle = oracle()

        query = f"""
            SELECT cod_empresa,eu.nome 
            FROM empresas_usuarios eu
            LEFT JOIN SISTEMA_ACESSO_FUNCAO saf ON 1=1
                AND saf.COD_FUNCAO = eu.COD_FUNCAO 
            WHERE 1=1
                AND eu.DEMITIDO <> 'S'
                AND lower(eu.EMAIl) = '{email}'
            GROUP BY eu.COD_EMPRESA, eu.nome
            ORDER BY eu.cod_empresa
        """
        cur_oracle.execute(query)
        rows = cur_oracle.fetchall()
        quem_alterou = rows[0][1]
        
        
        cod_empresa = str(id_evento)[:2]
        if cod_empresa not in ['11', '33']:
            return jsonify({'status': 'error', 'message': 'ID do evento inválido'}), 400
        cod_evento = str(id_evento)[2:]
        if not cod_evento.isdigit():
            return jsonify({'status': 'error', 'message': 'ID do evento inválido'}), 400
        cod_evento = int(cod_evento)
        
        query = f"""
            SELECT saf.COD_ACESSO 
            FROM empresas_usuarios eu
            LEFT JOIN SISTEMA_ACESSO_FUNCAO saf ON 1=1
                AND saf.COD_FUNCAO = eu.COD_FUNCAO 
            WHERE 1=1
                AND eu.DEMITIDO <> 'S'
                AND lower(eu.EMAIl) = '{email}'
                AND saf.COD_ACESSO = '80320'
            GROUP BY saf.COD_ACESSO
        """
        conn_oracle, cur_oracle = oracle()
        cur_oracle.execute(query)
        rows = cur_oracle.fetchall()
        filter_responsavel = ''
        if len(rows) == 0:
            filter_responsavel = f" AND lower(eu.EMAIl) = '{email}' "
        
        query = f"""
            select ce.COD_PRODUTO, ce.COD_MODELO, pm.DESCRICAO_MODELO 
            from crm_eventos ce
            LEFT JOIN produtos_modelos pm ON 1=1
                AND pm.COD_PRODUTO = ce.COD_PRODUTO 
                AND pm .COD_MODELO = ce.COD_MODELO
            where 1=1
                and ce.cod_empresa = {cod_empresa}
                and ce.cod_evento = {cod_evento}
                
        """
        cur_oracle.execute(query)
        rows = cur_oracle.fetchall()
        if len(rows) == 0:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'Evento não encontrado'}), 404
        modelo_atual = f"{rows[0][2]}"
        if not modelo_atual or modelo_atual.strip() == '':
            modelo_atual = 'Não informado'
        
        query = f"""
            SELECT pm.DESCRICAO_MODELO, pm.COD_PRODUTO, pm.COD_MODELO 
                    FROM PRODUTOS_MODELOS pm
                    WHERE 1=1
                        and pm.internet = 'S'
                        and pm.COD_PRODUTO = {cod_produto}
                        and pm.COD_MODELO = {cod_modelo}
                    order by pm.descricao_modelo
        """
        cur_oracle.execute(query)
        rows = cur_oracle.fetchall()
        if len(rows) == 0:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'Modelo de veículo não encontrado'}), 404
        
        novo_modelo = f"{rows[0][0]}"
        
        query = f"""
            update crm_eventos
            set cod_produto = {cod_produto},
                cod_modelo = {cod_modelo}
            where cod_empresa = {cod_empresa}
            and cod_evento = {cod_evento}
        """
        cur_oracle.execute(query)
        query = f"""
            insert into crm_acoes
            (cod_empresa,cod_evento, responsavel, tipo_acao, data, observacao, status, cod_acao, quem_criou)
            values (
                {cod_empresa},
                {cod_evento},
                '{quem_alterou}',
                5,
                SYSDATE,
                'Modelo de veículo alterado de: {modelo_atual} para {novo_modelo}',
                'P',
                seq_crm_COD_ACAO.nextval,
                '{quem_alterou}'
            )
        """
        cur_oracle.execute(query)
        conn_oracle.commit()
        cur_oracle.close()
        conn_oracle.close()
        retorno = {}
        retorno['status'] = 'success'
        retorno['message'] = 'Temperatura do evento atualizada com sucesso'
        return jsonify(retorno), 200
    except Exception as e:
        try:
            conn_oracle.rollback()
            cur_oracle.close()
            conn_oracle.close()
        except:
            pass
        return jsonify({'status': 'error', 'message': str(e)}), 500


    try:
        now = datetime.now().strftime("%Y-%m-%d")
        list_status = ['P','E','D','V','A','R','CP']
        token_data = request.token_data
        email = token_data.get('email').strip().lower()
        status = request.args.get('status', None)
        tipo_evento = request.args.get('tipo_evento', None)
        initial_date = request.args.get('initial_date', None)
        final_date = request.args.get('final_date', None)
        current_page = int(request.args.get('current_page', 1))
        search = request.args.get('search', None)
        limit = int(request.args.get('limit', 10))
        retorno = {}
        
        filter_tipo_evento = ''
        if tipo_evento:
            tipo_evento = tipo_evento.split(',')
            for te in tipo_evento:
                if not te.isdigit():
                    return jsonify({'status': 'error', 'message': f'Tipo de evento inválido: {te}'}), 400
            tipo_evento = ",".join(tipo_evento)
            filter_tipo_evento = f" AND ce.COD_TIPO_EVENTO IN ({tipo_evento}) "
        
        filter_initial_date = ''
        filter_final_date = ''
        if initial_date:
            try:
                datetime.strptime(initial_date, '%Y-%m-%d')
                filter_initial_date = f" AND TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) >= TO_DATE('{initial_date}', 'YYYY-MM-DD') "
            except ValueError:
                return jsonify({'status': 'error', 'message': 'Data inicial inválida. Use o formato YYYY-MM-DD'}), 400
        
        if final_date:
            try:
                datetime.strptime(final_date, '%Y-%m-%d')
                filter_final_date = f" AND TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) <= TO_DATE('{final_date}', 'YYYY-MM-DD')"
            except ValueError:
                return jsonify({'status': 'error', 'message': 'Data final inválida. Use o formato YYYY-MM-DD'}), 400
        
        
        filter_status = ''
        if status:
            status = status.split(',')
            for s in status:
                if s not in list_status:
                    return jsonify({'status': 'error', 'message': f'Status inválido: {s}'}), 400
            status = "','".join(status)
            status = f"('{status}')"
            status = status.replace("''","'")
            status = status.replace("'(","(")
            status = status.replace(")'",")")
            filter_status = f""" AND (
                                CASE
                                    WHEN ce.cod_motivo_perda IS NOT NULL AND ce.status = 'E' THEN 'CP'
                                    ELSE ce.status
                                END
                            ) IN {status}"""
        
        if search:
            search = search.replace("'", "''").lower()
            filter_search = f"""
                AND (
                    LOWER(ce.RESPONSAVEL_PELO_EVENTO) LIKE '%{search.lower()}%'
                    OR LOWER(ce.NOME_CLIENTE_AVULSO) LIKE '%{search.lower()}%'
                    OR LOWER(c.NOME) LIKE '%{search.lower()}%'
                    OR LOWER(c.EMAIL_NFE) LIKE '%{search.lower()}%'
                    OR LOWER(ce.EMAIL_CLIENTE_AVULSO) LIKE '%{search.lower()}%'
                    OR LOWER(ce.FONE_CLIENTE_AVULSO) LIKE '%{search.lower()}%'
                    OR LOWER(concat(c.PREFIXO_CEL,c.TELEFONE_CEL)) LIKE '%{search.lower()}%'
                    OR LOWER(concat(c.PREFIXO_RES,c.TELEFONE_RES)) LIKE '%{search.lower()}%'
                    OR LOWER(concat(c.PREFIXO_COM,c.TELEFONE_COM)) LIKE '%{search.lower()}%'
                    OR LOWER(concat(c.PREFIXO_FAX,c.TELEFONE_FAX)) LIKE '%{search.lower()}%'
                    OR LOWER(concat(c.PREFIXO_MSG_TXT_INST,c.NUMERO_MSG_TXT_INST)) LIKE '%{search.lower()}%'
                    OR LOWER(pm.DESCRICAO_MODELO) LIKE '%{search.lower()}%'
                    OR TO_CHAR(ce.COD_EVENTO) = '{search}'
                )
            """
        
        
        
        query = f"""
            SELECT saf.COD_ACESSO 
            FROM empresas_usuarios eu
            LEFT JOIN SISTEMA_ACESSO_FUNCAO saf ON 1=1
                AND saf.COD_FUNCAO = eu.COD_FUNCAO 
            WHERE 1=1
                AND eu.DEMITIDO <> 'S'
                AND lower(eu.EMAIl) = '{email}'
                AND saf.COD_ACESSO = '80320'
            GROUP BY saf.COD_ACESSO
        """
        conn_oracle, cur_oracle = oracle()
        cur_oracle.execute(query)
        rows = cur_oracle.fetchall()
        filter_responsavel = ''
        if len(rows) == 0:
            filter_responsavel = f" AND lower(eu.EMAIl) = '{email}' "
        
        query = f"""
                SELECT
                    count(*)
                FROM
                    CRM_EVENTOS ce
                LEFT JOIN EMPRESAS_USUARIOS eu ON
                    1 = 1
                    AND eu.nome = ce.RESPONSAVEL_PELO_EVENTO
                LEFT JOIN CRM_ANDAMENTO ca ON
                    1 = 1
                    AND ca.COD_ANDAMENTO = ce.COD_ANDAMENTO
                LEFT JOIN MIDIA m ON
                    1=1
                    AND m.COD_MIDIA = ce.COD_MIDIA 
                LEFT JOIN clientes c ON
                    1 = 1
                    AND ce.COD_CLIENTE = c.COD_CLIENTE
                LEFT JOIN CRM_EVENTOS_TIPO cet ON 1=1
                    AND cet.COD_TIPO_EVENTO = ce.COD_TIPO_EVENTO
                LEFT JOIN CRM_DESCARTES cd on 1=1
                    and cd.COD_DESCARTE = ce.COD_DESCARTE
                LEFT JOIN CRM_MOTIVO_PERDAS cmp ON 1=1
                    AND cmp.cod_motivo_perda = ce.cod_motivo_perda
                LEFT JOIN produtos_modelos pm ON pm.COD_PRODUTO = ce.COD_PRODUTO AND pm.COD_MODELO = ce.COD_MODELO 
                WHERE
                    1 = 1
                    --AND ce.COD_TIPO_EVENTO IN (785)
                    {filter_responsavel}
                    {filter_status}
                    {filter_search if search else ''}
                    {filter_initial_date}
                    {filter_final_date}
                    {filter_tipo_evento}
                    --AND TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) >= TO_DATE('{initial_date}', 'YYYY-MM-DD')
                    --AND TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) <= TO_DATE('{final_date}', 'YYYY-MM-DD')
        """
        # return query
        cur_oracle.execute(query)
        total = cur_oracle.fetchone()[0]
        if total == 0:
            return jsonify({'status': 'error', 'message': 'Não tem eventos showroom no período'}), 404
        offset = (current_page - 1) * limit
        total_pages = (total + limit - 1) // limit
        start_row = (current_page - 1) * limit + 1
        end_row = current_page * limit
        if current_page > total_pages:
            return jsonify({'status': 'error', 'message': 'Página inválida'}), 400
        query =f"""
            SELECT *
            FROM (
                SELECT t.*, ROWNUM AS rn
                FROM (
                    -- Sua query original com ORDER BY aqui dentro
                    SELECT
                        CASE
                            WHEN ce.cod_motivo_perda IS NOT null AND ce.status = 'E' THEN 'CP'
                            ELSE ce.status
                        END status,
                        TO_CHAR(ce.DATA_CRIACAO, 'YYYY-MM-DD HH24:MI:SS') AS DATA_CRIACAO,
                        TO_CHAR(
                            CASE
                                WHEN ce.data_novo_contato IS NULL THEN ce.data_evento
                                ELSE ce.data_novo_contato
                            END, 'YYYY-MM-DD HH24:MI:SS'
                        ) AS data_contato,
                        ce.COD_EVENTO,
                        ce.COD_EMPRESA,
                        cet.DESC_TIPO_EVENTO,
                        ca.ANDAMENTO,
                        ce.COD_CLIENTE,
                        CASE
                            WHEN ce.COD_CLIENTE = 1 THEN ce.NOME_CLIENTE_AVULSO 
                            ELSE c.NOME 
                        END nome_cliente,
                        concat(c.PREFIXO_CEL,c.TELEFONE_CEL) tel_cel,
                        ce.fone_cliente_avulso,
                        ce.email_cliente_avulso,
                        c.EMAIL_NFE,
                        ce.TERMOMETRO,
                        ce.OBS_MEMO,
                        cmp.desc_motivo motivo_perda,
                        cd.descricao_descarte,
                        ce.RESPONSAVEL_PELO_EVENTO,
                        eu.NOME_COMPLETO RESPONSAVEL_NOME_COMPLETO,
                        pm.descricao_modelo,
                        concat(c.PREFIXO_RES,c.TELEFONE_RES) tel_residencial,
                        concat(c.PREFIXO_COM,c.TELEFONE_COM) tel_comercial,
                        concat(c.PREFIXO_FAX,c.TELEFONE_FAX) tel_fax,
                        concat(c.PREFIXO_MSG_TXT_INST,c.NUMERO_MSG_TXT_INST) tel_whatsapp,
                        ce.data_agendada,
                        ce.data_visita,
                        CASE
			                -- Se a data/hora do contato for anterior a data/hora atual, está ATRASADO
			                WHEN (
			                    CASE
			                        WHEN ce.data_novo_contato IS NULL THEN ce.data_evento
			                        ELSE ce.data_novo_contato
			                    END
			                ) < SYSDATE THEN 'ATRASADO'
			                -- Se a data do contato (ignorando a hora) for maior que a data de hoje, é Futuro
			                WHEN TRUNC(
			                    CASE
			                        WHEN ce.data_novo_contato IS NULL THEN ce.data_evento
			                        ELSE ce.data_novo_contato
			                    END
			                ) > TRUNC(SYSDATE) THEN 'FUTURO'
			                -- Caso contrário, é para hoje (de agora até o fim do dia)
			                ELSE 'TRABALHANDO'
			            END AS status_atendimento
                    FROM
                        CRM_EVENTOS ce
                    LEFT JOIN EMPRESAS_USUARIOS eu ON eu.nome = ce.RESPONSAVEL_PELO_EVENTO
                    LEFT JOIN CRM_ANDAMENTO ca ON ca.COD_ANDAMENTO = ce.COD_ANDAMENTO
                    LEFT JOIN MIDIA m ON m.COD_MIDIA = ce.COD_MIDIA 
                    LEFT JOIN clientes c ON ce.COD_CLIENTE = c.COD_CLIENTE
                    LEFT JOIN CRM_EVENTOS_TIPO cet ON cet.COD_TIPO_EVENTO = ce.COD_TIPO_EVENTO
                    LEFT JOIN CRM_DESCARTES cd on cd.COD_DESCARTE = ce.COD_DESCARTE
                    LEFT JOIN CRM_MOTIVO_PERDAS cmp ON cmp.cod_motivo_perda = ce.cod_motivo_perda
                    LEFT JOIN produtos_modelos pm ON pm.COD_PRODUTO = ce.COD_PRODUTO AND pm.COD_MODELO = ce.COD_MODELO 
                    WHERE
                        1 = 1
                        --AND ce.COD_TIPO_EVENTO IN (785)
                        {filter_tipo_evento}
                        {filter_responsavel}
                        {filter_status}
                        {filter_search if search else ''}
                        {filter_initial_date}
                        {filter_final_date}
                        --AND TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) >= TO_DATE('{initial_date}', 'YYYY-MM-DD')
                        --AND TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) <= TO_DATE('{final_date}', 'YYYY-MM-DD')
                    ORDER BY
                        3
                ) t
            )
            WHERE
                rn BETWEEN {start_row} AND {end_row}
        """
        # return query
        cur_oracle.execute(query)
        rows = cur_oracle.fetchall()
        retorno['total_eventos'] = total
        retorno['total_pages'] = total_pages
        retorno['current_page'] = current_page
        retorno['eventos'] = []
        for row in rows:
            if row[1]:  # data_criacao
                try:
                    data_criacao_obj = datetime.strptime(row[1], '%Y-%m-%d %H:%M:%S')
                    data_criacao_iso = data_criacao_obj.isoformat()
                except:
                    data_criacao_iso = row[1]  # fallback para string original
            
            if row[2]:  # data_contato
                try:
                    data_contato_obj = datetime.strptime(row[2], '%Y-%m-%d %H:%M:%S')
                    data_contato_iso = data_contato_obj.isoformat()
                except:
                    data_contato_iso = row[2]  # fallback para string original
            if row[24]:  # data_agendada
                try:
                    data_agendada_obj = datetime.strptime(row[24], '%Y-%m-%d %H:%M:%S')
                    data_agendada_iso = data_agendada_obj.isoformat()
                except:
                    data_agendada_iso = row[24]  # fallback para string original
            if row[25]:  # data_visita
                try:
                    data_visita_obj = datetime.strptime(row[25], '%Y-%m-%d %H:%M:%S')
                    data_visita_iso = data_visita_obj.isoformat()
                except:
                    data_visita_iso = row[25]  # fallback para string original
            obs_memo_processado = processar_obs_memo(row[14])

            retorno['eventos'].append({  
                'status': row[0],
                'data_criacao': data_criacao_iso,
                'data_contato': data_contato_iso,
                'cod_evento': row[3],
                'cod_empresa': row[4],
                'desc_tipo_evento': row[5],
                'andamento': row[6],
                'cod_cliente': row[7],
                'nome_cliente': row[8],
                'tel_cel': row[9],
                'fone_cliente_avulso': row[10],
                'email_cliente_avulso': row[11],
                'email_nfe': row[12],
                'termometro': row[13],
                'obs_memo': obs_memo_processado,
                'motivo_perda': row[15],
                'descricao_descarte': row[16],
                'responsavel_pelo_evento': row[17],
                'responsavel_nome_completo': row[18],
                'descricao_modelo': row[19],
                'tel_residencial': row[20],
                'tel_comercial': row[21],
                'tel_fax': row[22],
                'tel_whatsapp': row[23],
                'data_agendada': data_agendada_iso if row[24] else None,
                'data_visita': data_visita_iso if row[25] else None,
                'status_atendimento': row[26]
            })
        cur_oracle.close()
        conn_oracle.close()

        return jsonify(retorno), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@crm_bp.route('/api/crm/eventos/muda_midia/<int:id_evento>', methods=['PUT'])
@token_required
def crm_eventos_muda_midia(id_evento):
    try:
        token_data = request.token_data
        email = token_data.get('email').strip().lower()
        cod_empresa = str(id_evento)[:2]
        cod_evento = str(id_evento)[2:]
        if cod_empresa not in ['11', '33']:
            return jsonify({'status': 'error', 'message': 'ID do evento inválido'}), 400
        if not cod_evento.isdigit():
            return jsonify({'status': 'error', 'message': 'ID do evento inválido'}), 400
        cod_evento = int(cod_evento)
        cod_midia = request.json.get('cod_midia', None)
        if not cod_midia or not str(cod_midia).isdigit():
            return jsonify({'status': 'error', 'message': 'Código da mídia é obrigatório'}), 400
        cod_midia = int(cod_midia)
        
        query = f"""
            SELECT cod_empresa,eu.nome 
            FROM empresas_usuarios eu
            LEFT JOIN SISTEMA_ACESSO_FUNCAO saf ON 1=1
                AND saf.COD_FUNCAO = eu.COD_FUNCAO 
            WHERE 1=1
                AND eu.DEMITIDO <> 'S'
                AND lower(eu.EMAIl) = '{email}'
            GROUP BY eu.COD_EMPRESA, eu.nome
            ORDER BY eu.cod_empresa
        """
        conn_oracle, cur_oracle = oracle()
        cur_oracle.execute(query)
        rows = cur_oracle.fetchall()
        quem_criou = rows[0][1]
        filter_responsavel = ''
        if len(rows) == 0:
            filter_responsavel = f" AND lower(eu.EMAIl) = '{email}' "
        
        
        
        query = f"""
            select data_criacao
            from crm_eventos ce
            where 1=1
                and ce.cod_empresa = {cod_empresa}
                and ce.cod_evento = {cod_evento}
                {filter_responsavel}
        """
        cur_oracle.execute(query)
        rows = cur_oracle.fetchall()
        if len(rows) == 0:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'Evento não encontrado'}), 404
        
        query = f"""
            SELECT cod_midia, descricao FROM midia
            WHERE 1=1
                AND (ativo = 'S' OR ativo IS NULL)
                and cod_midia = {cod_midia}
        """
        cur_oracle.execute(query)
        rows = cur_oracle.fetchall()
        if len(rows) == 0:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'Mídias não encontradas'}), 404
        nome_midia = rows[0][1]
        
        
        query = f"""
            update crm_eventos
            set cod_midia = {cod_midia}
            where cod_empresa = {cod_empresa}
            and cod_evento = {cod_evento}
        """
        cur_oracle.execute(query)
        
        query = f"""
            insert into crm_acoes
            (cod_empresa,cod_evento, responsavel, tipo_acao, data, observacao, status, cod_acao, quem_criou)
            values (
                {cod_empresa},
                {cod_evento},
                '{quem_criou}',
                136,
                SYSDATE,
                'Mídia alterada para: {nome_midia}',
                'P',
                seq_crm_COD_ACAO.nextval,
                '{quem_criou}'
            )
        """
        
        
        
        cur_oracle.execute(query)
        conn_oracle.commit()
        cur_oracle.close()
        conn_oracle.close()
        retorno = {}
        retorno['status'] = 'success'
        retorno['message'] = 'Mídia do evento atualizada com sucesso'
        return jsonify(retorno), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@crm_bp.route('/api/crm/eventos/muda_tipo_evento/<int:id_evento>', methods=['PUT'])
@token_required
def crm_eventos_muda_tipo_evento(id_evento):
    try:
        token_data = request.token_data
        email = token_data.get('email').strip().lower()
        cod_empresa = str(id_evento)[:2]
        cod_evento = str(id_evento)[2:]
        if cod_empresa not in ['11', '33']:
            return jsonify({'status': 'error', 'message': 'ID do evento inválido'}), 400
        if not cod_evento.isdigit():
            return jsonify({'status': 'error', 'message': 'ID do evento inválido'}), 400
        cod_evento = int(cod_evento)
        cod_tipo_evento = request.json.get('cod_tipo_evento', None)
        if not cod_tipo_evento or not str(cod_tipo_evento).isdigit():
            return jsonify({'status': 'error', 'message': 'Código do tipo de evento é obrigatório'}), 400
        cod_tipo_evento = int(cod_tipo_evento)
        
        query = f"""
            SELECT cod_empresa,eu.nome 
            FROM empresas_usuarios eu
            LEFT JOIN SISTEMA_ACESSO_FUNCAO saf ON 1=1
                AND saf.COD_FUNCAO = eu.COD_FUNCAO 
            WHERE 1=1
                AND eu.DEMITIDO <> 'S'
                AND lower(eu.EMAIl) = '{email}'
            GROUP BY eu.COD_EMPRESA, eu.nome
            ORDER BY eu.cod_empresa
        """
        conn_oracle, cur_oracle = oracle()
        cur_oracle.execute(query)
        rows = cur_oracle.fetchall()
        quem_criou = rows[0][1]
        filter_responsavel = ''
        if len(rows) == 0:
            filter_responsavel = f" AND lower(eu.EMAIl) = '{email}' "
        
        
        
        query = f"""
            select data_criacao
            from crm_eventos ce
            where 1=1
                and ce.cod_empresa = {cod_empresa}
                and ce.cod_evento = {cod_evento}
                {filter_responsavel}
        """
        cur_oracle.execute(query)
        rows = cur_oracle.fetchall()
        if len(rows) == 0:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'Evento não encontrado'}), 404

        query = f"""
            select cet.cod_tipo_evento, cet.desc_tipo_evento
            from crm_eventos_tipo cet
            where 1=1
                and cet.ativo = 'S'
                and cet.cod_tipo_evento = {cod_tipo_evento}
        """
        cur_oracle.execute(query)
        rows = cur_oracle.fetchall()
        if len(rows) == 0:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'Tipo de evento não encontrado'}), 404
        nome_tipo_evento = rows[0][1]

        query = f"""
            update crm_eventos
            set cod_tipo_evento = {cod_tipo_evento}
            where cod_empresa = {cod_empresa}
            and cod_evento = {cod_evento}
        """
        cur_oracle.execute(query)

        query = f"""
            insert into crm_acoes
            (cod_empresa,cod_evento, responsavel, tipo_acao, data, observacao, status, cod_acao, quem_criou)
            values (
                {cod_empresa},
                {cod_evento},
                '{quem_criou}',
                136,
                SYSDATE,
                'Tipo de evento alterado para: {nome_tipo_evento}',
                'P',
                seq_crm_COD_ACAO.nextval,
                '{quem_criou}'
            )
        """
        cur_oracle.execute(query)
        conn_oracle.commit()
        cur_oracle.close()
        conn_oracle.close()
        retorno = {}
        retorno['status'] = 'success'
        retorno['message'] = 'Tipo de evento atualizado com sucesso'
        return jsonify(retorno), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@crm_bp.route('/api/crm/eventos_tipo', methods=['GET'])
@token_required
def list_eventos_tipo():
    try:
        conn_oracle, cur_oracle = oracle()
        query = f"""
            select cet.cod_tipo_evento, cet.desc_tipo_evento 
            from crm_eventos_tipo cet
            where 1=1
                and cet.ativo = 'S'
            order by cet.cod_area desc, cet.desc_tipo_evento
        """
        cur_oracle.execute(query)
        rows = cur_oracle.fetchall()
        eventos_tipo = []
        for row in rows:
            eventos_tipo.append({
                'cod_tipo_evento': row[0],
                'desc_tipo_evento': row[1]
            })
        cur_oracle.close()
        conn_oracle.close()
        return jsonify({'status': 'success', 'eventos_tipo': eventos_tipo}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
@crm_bp.route('/api/crm/midias', methods=['GET'])
@token_required
def list_midias():
    try:
        conn_oracle, cur_oracle = oracle()
        query = f"""
            select m.cod_midia, m.descricao
            from midia m
            where ativo = ('S') or ativo is null
            order by m.descricao
        """
        cur_oracle.execute(query)
        rows = cur_oracle.fetchall()
        midias = []
        for row in rows:
            midias.append({
                'cod_midia': row[0],
                'descricao': row[1]
            })
        cur_oracle.close()
        conn_oracle.close()
        return jsonify({'status': 'success', 'midias': midias}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
