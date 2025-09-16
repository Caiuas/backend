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
    com data, usuario e observação
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
        
        observacao_texto = obs_memo[start_pos:end_pos].strip()
        
        # Remover \r e \n extras
        observacao_texto = observacao_texto.replace('\r', '').replace('\n', '').strip()
        
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

@crm_bp.route('/api/crm_andamentos', methods=['GET'])
def get_crm_andamentos():
    try:
        return 'oi'
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
        
@crm_bp.route('/api/crm/eventos_showroom', methods=['GET'])
@token_required
def list_crm_eventos_showroom():
    try:
        now = datetime.now().strftime("%Y-%m-%d")
        list_status = ['P','E','D','V']
        token_data = request.token_data
        email = token_data.get('email').strip().lower()
        status = request.args.get('status', 'P').upper()
        initial_date = request.args.get('initial_date', now)
        final_date = request.args.get('final_date', now)
        current_page = int(request.args.get('current_page', 1))
        limit = int(request.args.get('limit', 10))
        retorno = {}
        status = status.split(',')
        for s in status:
            if s not in list_status:
                return jsonify({'status': 'error', 'message': f'Status inválido: {s}'}), 400
        status = "','".join(status)
        status = f"('{status}')"
        status = status.replace("''","'")
        status = status.replace("'(","(")
        status = status.replace(")'",")")
        
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
        filter_status = f" AND ce.status in {status}"
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
                    AND ce.COD_TIPO_EVENTO IN (785)
                    {filter_responsavel}
                    {filter_status}
                    AND TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) >= TO_DATE('{initial_date}', 'YYYY-MM-DD')
                    AND TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) <= TO_DATE('{final_date}', 'YYYY-MM-DD')
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
                        ce.STATUS,
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
                        pm.descricao_modelo
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
                        AND ce.COD_TIPO_EVENTO IN (785)
                        {filter_responsavel}
                        {filter_status}
                        AND TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) >= TO_DATE('{initial_date}', 'YYYY-MM-DD')
                        AND TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) <= TO_DATE('{final_date}', 'YYYY-MM-DD')
                    ORDER BY
                        3 DESC
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
                'descricao_modelo': row[19]
            })
        cur_oracle.close()
        conn_oracle.close()

        return jsonify(retorno), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    