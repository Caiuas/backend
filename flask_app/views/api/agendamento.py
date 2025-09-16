from flask import Blueprint, jsonify, request
from database import oracle, chatwoot
from dotenv import load_dotenv
from datetime import datetime
import os
import jwt
load_dotenv()

agendamento_bp = Blueprint('agendamento', __name__)

@agendamento_bp.route('/api/agenda', methods=['GET'])
def get_agendamento():
    try:
        date = request.args.get('date')
        cod_empresa = request.args.get('cod_empresa')
        retorno = {}
        conn_oracle, cur_oracle = oracle()
        if date is None or cod_empresa is None:
            return jsonify({'status': 'error', 'message': 'Missing required parameters: date and cod_empresa'}), 400
        if not cod_empresa.isdigit():
            return jsonify({'status': 'error', 'message': 'cod_empresa must be a number'}), 400
        try:
            date = datetime.strptime(date, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'status': 'error', 'message': 'Invalid date format. Use YYYY-MM-DD.'}), 400
        query = f"""
                    SELECT 
                        ps2.cod_empresa,
                        ps2.agenda_hora_comeca,
                        ps2.agenda_hora_fim,
                        ps2.agenda_intervalo
                    FROM
                        parm_sys2 ps2,
                        parm_sys3,
                        empresas emp
                    WHERE
                        (emp.Cod_Empresa = ps2.cod_empresa)
                        AND (ps2.cod_empresa = parm_sys3.cod_empresa)
                        and ps2.cod_empresa = {cod_empresa}
        """
        cur_oracle.execute(query)
        result = cur_oracle.fetchall()
        if len(result) == 0:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'No data found for the given parameters'}), 404
        retorno['parametros'] = {}
        retorno['parametros']['cod_empresa'] = result[0][0]
        retorno['parametros']['agenda_hora_comeca'] = datetime.strptime(str(result[0][1]), '%Y-%m-%d %H:%M:%S').isoformat()
        retorno['parametros']['agenda_hora_fim'] = datetime.strptime(str(result[0][2]), '%Y-%m-%d %H:%M:%S').isoformat()
        retorno['parametros']['agenda_intervalo'] = result[0][3]

        query = f"""
            select b.prisma, b.descricao, b.cod_empresa_filtro cod_empresa
            from prisma_box b
            where b.agenda = 'S'
            and b.cod_empresa_filtro = {cod_empresa}
            order by prisma
        """
        cur_oracle.execute(query)
        result = cur_oracle.fetchall()
        retorno['prisma'] = []
        for row in result:
            retorno['prisma'].append({
                'prisma': row[0],
                'descricao': row[1],
                'cod_empresa': row[2]
            })
        
        query = f"""
        select 
            s.cod_empresa, 
            s.cod_os_agenda, 
            c.NOME,
            s.CRM_COD_EVENTO,
            ce.RESPONSAVEL_PELO_EVENTO,
            eu.NOME_COMPLETO,
            pb.DESCRICAO,
            oa.PLACA,
            pm.DESCRICAO_MODELO,
            oa.PRISMA,
            s.data_comeca, 
            s.data_fim,
            o.numero_os,
            oa.consultor,
            eu2.COD_FUNCAO,
            eu2.nome_completo,
            oa.SERVICO_EXPRESSO,
            oa.status_agenda
        from os_agenda_servicos s
        LEFT JOIN CRM_EVENTOS ce ON 1=1
            AND ce.COD_EMPRESA = s.crm_cod_empresa 
            AND ce.COD_EVENTO = s.CRM_COD_EVENTO 
        LEFT JOIN OS_AGENDA oa ON 1=1
            AND oa.COD_EMPRESA = s.COD_EMPRESA 
            AND oa.COD_OS_AGENDA = s.COD_OS_AGENDA 
        LEFT JOIN CLIENTES c ON 1=1
            AND c.COD_CLIENTE = oa.cod_cliente
        LEFT JOIN PRISMA_BOX pb ON 1=1
            AND pb.PRISMA = oa.PRISMA 
        LEFT JOIN produtos p ON 1=1
            AND p.COD_PRODUTO = oa.COD_PRODUTO 
        LEFT JOIN PRODUTOS_MODELOS pm ON 1=1
            AND pm.COD_PRODUTO = oa.COD_PRODUTO 
            AND pm.COD_MODELO = oa.COD_MODELO
        LEFT JOIN EMPRESAS_USUARIOS eu ON 1=1
	        AND eu.nome = ce.RESPONSAVEL_PELO_EVENTO
        LEFT JOIN os o ON 1=1
	    	AND oa.COD_EMPRESA = o.COD_EMPRESA 
            AND oa.COD_OS_AGENDA = o.COD_OS_AGENDA
            --and o.complemento <> 'S'
            AND o.ORCAMENTO <> 'S'
        LEFT JOIN empresas_usuarios eu2 ON 1=1
        	AND eu2.NOME = oa.CONSULTOR
        LEFT JOIN empresas_usuarios eu3 ON 1=1
	        AND eu3.NOME = oa.quem_abriu
        where 
            pb.COD_EMPRESA_FILTRO = {cod_empresa}
            AND oa.PRISMA IS NOT null
            and   trunc(s.data_comeca) <=  trunc(TO_DATE('{date}', 'YYYY-MM-DD'))
            and   trunc(s.data_fim) >= trunc(TO_DATE('{date}', 'YYYY-MM-DD'))
        order by s.data_comeca
        """
        cur_oracle.execute(query)
        result = cur_oracle.fetchall()
        retorno['agendamentos'] = []
        for row in result:
            data_comeca = datetime.strptime(str(row[10]), '%Y-%m-%d %H:%M:%S')
            data_fim = datetime.strptime(str(row[11]), '%Y-%m-%d %H:%M:%S')       
            retorno['agendamentos'].append({
                'cod_empresa': row[0],
                'cod_os_agenda': row[1],
                'nome_cliente': row[2],
                'crm_cod_evento': row[3],
                'responsavel_pelo_evento': row[4],
                'responsavel_agendamento': str(row[5]).replace("\n", "") if row[5] else None,
                'mesa': row[6],
                'placa': row[7],
                'descricao_modelo': row[8],
                'prisma': row[9],
                'data_comeca': data_comeca.isoformat() if data_comeca else None,
                'data_fim': data_fim.isoformat() if data_fim else None,
                'numero_os': row[12],
                'consultor': row[13]  if row[14] in (26,38) else None,
                'nome_consultor': row[15] if row[14] in (26,38) else None,
                'express': row[16] if row[16] else None,
                'status_agenda': row[17] if row[17] else None,
                'reclamacoes': [],
                'tags': [],
                'whatsapp': []
            })
        for agenda in retorno['agendamentos']:
            query = f"""
            SELECT oar.DESCRICAO
                FROM OS_AGENDA_RECLAMACAO oar 
                WHERE cod_empresa = {agenda['cod_empresa']}
                AND COD_OS_AGENDA = {agenda['cod_os_agenda']}
                ORDER BY cod_os_agenda DESC
            """
            cur_oracle.execute(query)
            result = cur_oracle.fetchall()
            for row in result:
                agenda['reclamacoes'].append({
                    'descricao': row[0]
                })
        for agenda in retorno['agendamentos']:
            query = f"""
           SELECT ct.name, ct.id_tag, oat.ID_TAG_OS_AGENDA
                FROM caiuas_os_agenda_tags oat
                LEFT JOIN caiuas_tags ct ON oat.id_tag = ct.id_tag
                WHERE oat.cod_empresa = {agenda['cod_empresa']}
                AND oat.cod_os_agenda = {agenda['cod_os_agenda']}
            """
            cur_oracle.execute(query)
            result = cur_oracle.fetchall()
            for row in result:
                agenda['tags'].append({
                    'name': row[0],
                    'id_tag': row[1],
                    'id_tag_os_agenda': row[2]
                })
        
        for agenda in retorno['agendamentos']:
            query = f"""
            SELECT id_log, name, status, TO_CHAR(UPDATED_AT, 'YYYY-MM-DD"T"HH24:MI:SS') AS UPDATED_AT_ISO
                FROM CAIUAS_LOG_WHATSAPP clw 
                WHERE 1=1
                    AND clw.COD_EMPRESA = {agenda['cod_empresa']}
                    AND clw.COD_OS_AGENDA = {agenda['cod_os_agenda']}
            """
            cur_oracle.execute(query)
            result = cur_oracle.fetchall()
            # agenda['whatsapp'] = []
            for row in result:
                # return str(row[3])
                updated_at = datetime.strptime(str(row[3]), '%Y-%m-%dT%H:%M:%S')
                agenda['whatsapp'].append({
                    'id_log': row[0],
                    'name': row[1],
                    'status': row[2],
                    'updated_at': updated_at.isoformat() if updated_at else None
                })
            
        query = f"""
         Select pbr.data_comeca, pbr.data_termina, pbr.motivo,pbr.prisma
            from prisma_box_reserva pbr                                 
            WHERE 1=1
                and trunc(pbr.data_comeca) = TO_DATE('2025-07-01', 'YYYY-MM-DD')
        """
        cur_oracle.execute(query)
        result = cur_oracle.fetchall()
        retorno['reservas'] = []
        for row in result:
            data_comeca = datetime.strptime(str(row[0]), '%Y-%m-%d %H:%M:%S')
            data_fim = datetime.strptime(str(row[1]), '%Y-%m-%d %H:%M:%S')       
            retorno['reservas'].append({
                'data_comeca': data_comeca.isoformat() if data_comeca else None,
                'data_fim': data_fim.isoformat() if data_fim else None,
                'motivo': row[2],
                'prisma': row[3]
            }) 
        cur_oracle.close()
        conn_oracle.close()
        return jsonify(retorno), 200
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@agendamento_bp.route('/api/consultor_agenda/<int:cod_empresa>', methods=['GET'])
def get_consutor_agenda(cod_empresa):
    try:
        query = f"""
        SELECT nome, nome_completo
            FROM EMPRESAS_USUARIOS eu 
            WHERE cod_funcao IN (38,26)
            AND cod_empresa = {cod_empresa}
        """
        conn_oracle, cur_oracle = oracle()
        cur_oracle.execute(query)
        result = cur_oracle.fetchall()
        if len(result) == 0:
            return jsonify({'status': 'error', 'message': 'No consultants found for the given company code'}), 404
        retorno = {}
        retorno['consultores'] = []
        for row in result:
            retorno['consultores'].append({
                'nome': row[0],
                'nome_completo': row[1]
            })
        return jsonify(retorno), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400
    
@agendamento_bp.route('/api/agenda/muda_consultor', methods=['POST'])
def muda_consultor():
    try:
        data = request.get_json()
        if 'cod_empresa' not in data or 'cod_os_agenda' not in data or 'consultor' not in data:
            return jsonify({'status': 'error', 'message': 'Missing required parameters: cod_empresa, cod_os_agenda, and consultor'}), 400
        
        if int(data['cod_empresa']) not in (11,33):
            return jsonify({'status': 'error', 'message': 'Invalid company code. Only 11 and 33 are allowed.'}), 400
        query = f"""
        select count(*) from empresas_usuarios eu
        where eu.cod_empresa = {data['cod_empresa']}
        and eu.nome = '{data['consultor']}'
        """
        conn_oracle, cur_oracle = oracle()
        cur_oracle.execute(query)
        result = cur_oracle.fetchone()
        if result[0] == 0:
            return jsonify({'status': 'error', 'message': 'Consultant not found for the given company code'}), 404
        
        query = f"""
        select count(*) from os_agenda oa
        where oa.cod_empresa = {data['cod_empresa']}
        and oa.cod_os_agenda = {data['cod_os_agenda']}
        """
        cur_oracle.execute(query)
        result = cur_oracle.fetchone()
        if result[0] == 0:
            return jsonify({'status': 'error', 'message': 'OS Agenda not found for the given company code and OS Agenda code'}), 404
        
        query = f"""
        UPDATE os_agenda
        set consultor = '{data['consultor']}'
        WHERE cod_empresa = {data['cod_empresa']}
        AND cod_os_agenda = {data['cod_os_agenda']}
        """
        cur_oracle.execute(query)
        conn_oracle.commit()
        retorno = {}
        retorno['status'] = 'success'
        retorno['message'] = 'Consultant updated successfully'
        
        return jsonify(data), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@agendamento_bp.route('/api/agenda/muda_agendador', methods=['POST'])
def muda_agendador():
    try:
        data = request.get_json()
        cod_empresa = data.get('cod_empresa')
        cod_os_agenda = data.get('cod_os_agenda')
        responsavel_pelo_evento = data.get('responsavel_pelo_evento')
        token = data.get('token')
        
        decoded = jwt.decode(token, os.environ.get('SECRET_KEY_BASE'), algorithms=['HS256'], options={"require": ["exp", "iat", "nbf" ]})
        
        if decoded['email'] not in ['pablo.ti@caiuas.com.br','angela.venancio@caiuas.com.br']:
            return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
        
        # with open('token.txt', 'w') as file:
        #     file.write(token)
        empresas = [11,33]
        if not cod_empresa or not cod_os_agenda or not responsavel_pelo_evento:
            return jsonify({'status': 'error', 'message': 'Missing required parameters: cod_empresa, cod_os_agenda, and responsavel_pelo_evento'}), 400
        
        if cod_empresa is None or cod_os_agenda is None or responsavel_pelo_evento is None:
            return jsonify({'status': 'error', 'message': 'Missing required parameters: cod_empresa, cod_os_agenda, and responsavel_pelo_evento'}), 400
        
        # if not isinstance(cod_empresa, int) or not isinstance(cod_os_agenda, int):
        #     return jsonify({'status': 'error', 'message': 'cod_empresa and cod_os_agenda must be numbers'}), 400
        try:
            cod_empresa = int(cod_empresa)
            cod_os_agenda = int(cod_os_agenda)
        except ValueError:
            return jsonify({'status': 'error', 'message': 'cod_empresa and cod_os_agenda must be numbers'}), 400
        if cod_empresa not in empresas:
            return jsonify({'status': 'error', 'message': 'Invalid company code. Only 11 and 33 are allowed.'}), 400
        query = f"""
            select count(*) from EMPRESAS_USUARIOS eu
            where 1=1
                and eu.cod_empresa = {cod_empresa}
                and eu.nome = '{responsavel_pelo_evento}'
        """
        conn_oracle, cur_oracle = oracle()
        cur_oracle.execute(query)
        result = cur_oracle.fetchone()
        if len(result) == 0 or result[0] == 0:
            return jsonify({'status': 'error', 'message': 'Responsável pelo evento não encontrado ou não atende essa empresa'}), 404
        query = f"""
            select CRM_COD_EVENTO from os_agenda oa
            where 1=1
                and oa.cod_empresa = {cod_empresa}
                and oa.cod_os_agenda = {cod_os_agenda}
        """
        cur_oracle.execute(query)
        result = cur_oracle.fetchall()
        if len(result) == 0:
            return jsonify({'status': 'error', 'message': 'Agendamento não encontrado'}), 404
        CRM_COD_EVENTO = result[0][0]
        if CRM_COD_EVENTO is None:
            return jsonify({'status': 'error', 'message': 'Agendamento não possui evento CRM associado'}), 400
        
        query = f"""
            UPDATE os_agenda 
            set quem_abriu = '{responsavel_pelo_evento}', quem_confirmou = '{responsavel_pelo_evento}'
            WHERE cod_empresa = {cod_empresa}
            AND cod_os_agenda = {cod_os_agenda}
        """
        cur_oracle.execute(query)
        query = f"""
            UPDATE CRM_EVENTOS
                set RESPONSAVEL_PELO_EVENTO = '{responsavel_pelo_evento}'
            WHERE COD_EMPRESA = {cod_empresa}
            AND COD_EVENTO = {CRM_COD_EVENTO}
        """
        cur_oracle.execute(query)
        conn_oracle.commit()
        cur_oracle.close()
        conn_oracle.close()
        return jsonify({'status': 'success', 'message': 'Agendador atualizado com sucesso'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@agendamento_bp.route('/api/os_agenda_tags', methods=['GET'])
def get_os_agenda_tags():
    try:
        conn, cur = oracle()
        query = """
        SELECT id_tag, name FROM caiuas_tags
        """
        cur.execute(query)
        result = cur.fetchall()
        if len(result) == 0:
            return jsonify({'status': 'error', 'message': 'No tags found'}), 404
        retorno = {}
        retorno['tags'] = []
        for row in result:
            retorno['tags'].append({
                'id_tag': row[0],
                'name': row[1]
            })
        return jsonify(retorno), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@agendamento_bp.route('/api/os_agenda_tags_unique', methods=['GET'])
def os_agenda_tags_unique():
    try:
        cod_empresa = request.args.get('cod_empresa')
        cod_os_agenda = request.args.get('cod_os_agenda')
        if cod_empresa is None or cod_os_agenda is None:
            return jsonify({'status': 'error', 'message': 'Missing required parameters: cod_empresa and cod_os_agenda'}), 400
        conn_oracle, cur_oracle = oracle()
        query = f"""
        SELECT DISTINCT ct.name, ct.id_tag
            FROM caiuas_os_agenda_tags oat
            LEFT JOIN caiuas_tags ct ON oat.id_tag = ct.id_tag
            WHERE oat.cod_empresa = {cod_empresa}
            AND oat.cod_os_agenda = {cod_os_agenda}
        """
        cur_oracle.execute(query)
        result = cur_oracle.fetchall()
        retorno = {}
        retorno['cod_empresa'] = cod_empresa
        retorno['cod_os_agenda'] = cod_os_agenda
        retorno['tags'] = []
        retorno['tags_disponiveis'] = []
        for row in result:
            retorno['tags'].append({
                'name': row[0],
                'id_tag': row[1]
            })
        query = f"""
        SELECT DISTINCT ct.name, ct.id_tag
            FROM caiuas_tags ct
        """
        cur_oracle.execute(query)
        result = cur_oracle.fetchall()
        for row in result:
            retorno['tags_disponiveis'].append({
                'name': row[0],
                'id_tag': row[1]
            })
        return jsonify(retorno), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@agendamento_bp.route('/api/add_tag_os_agenda', methods=['POST'])
def add_tag_os_agenda():
    try:
        data = request.get_json()
        if 'cod_empresa' not in data or 'cod_os_agenda' not in data or 'id_tag' not in data:
            return jsonify({'status': 'error', 'message': 'Missing required parameters: cod_empresa, cod_os_agenda, and id_tag'}), 400
        
        query = f"""
        SELECT count(*) FROM os_agenda 
        WHERE cod_empresa = {data['cod_empresa']}
        AND cod_os_agenda = {data['cod_os_agenda']}
        """
        
        conn_oracle, cur_oracle = oracle()
        cur_oracle.execute(query)
        result = cur_oracle.fetchone()
        if result[0] == 0:
            return jsonify({'status': 'error', 'message': 'OS Agenda not found for the given company code and OS Agenda code'}), 404
        
        query = f"""
        INSERT
                INTO
                caiuas_os_agenda_tags (id_tag_os_agenda,
                cod_empresa,
                cod_os_agenda,
                id_tag)
            VALUES (seq_caiuas_os_agenda_tags.NEXTVAL,
            {data['cod_empresa']},
            {data['cod_os_agenda']},
            {data['id_tag']})
        """
        try:
            cur_oracle.execute(query)
            conn_oracle.commit()
        except Exception as e:
            if 'CAIUAS_OS_AGENDA_TAGS_UNIQUE' in str(e):
                return jsonify({'status': 'error', 'message': 'Tag já está associada anteriormente'}), 400    
        return jsonify({'status': 'success', 'message': 'Tag added successfully'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400
    
@agendamento_bp.route('/api/remove_tag_os_agenda/<int:id_tag_os_agenda>', methods=['DELETE'])
def remove_tag_os_agenda(id_tag_os_agenda):
    try:
        query = f"""
        delete from caiuas_os_agenda_tags
        where id_tag_os_agenda = {id_tag_os_agenda}
        """
        # return query
        conn_oracle, cur_oracle = oracle()
        cur_oracle.execute(query)
        conn_oracle.commit()
        return jsonify({'status': 'success', 'message': 'Tag removed successfully'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@agendamento_bp.route('/api/agenda/send_whatsapp_confirmation', methods=['POST'])
def agenda_send_whatsapp_confirmation():
    try:
        data = request.get_json()
        if 'cod_empresa' not in data or 'cod_os_agenda' not in data or 'message' not in data:
            return jsonify({'status': 'error', 'message': 'Missing required parameters: cod_empresa, cod_os_agenda, and message'}), 400
        query = f"""
            select count(*) from os_agenda oa
            where oa.cod_empresa = {data['cod_empresa']}
            and oa.cod_os_agenda = {data['cod_os_agenda']}
        """
        conn_oracle, cur_oracle = oracle()
        cur_oracle.execute(query)
        result = cur_oracle.fetchone()
        if result[0] == 0:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'OS Agenda not found for the given company code and OS Agenda code'}), 404
        query = f"""
            INSERT
                INTO
                CAIUAS_LOG_WHATSAPP (ID_LOG,
                COD_EMPRESA,
                COD_OS_AGENDA,
                STATUS,
                NAME,
                UPDATED_AT)
            VALUES(SEQ_CRM_WHATSAPP_LOG.NEXTVAL, {data['cod_empresa']}, {data['cod_os_agenda']}, 'pendente', '{data['message']}', CURRENT_TIMESTAMP)
            """
        # return query
        cur_oracle.execute(query)
        conn_oracle.commit()
        cur_oracle.close()
        conn_oracle.close()
        return jsonify({'status': 'success', 'message': 'WhatsApp confirmation sent successfully'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400
    
@agendamento_bp.route('/api/agenda/confirm_visit', methods=['POST'])
def confirm_visit():
    try:
        data = request.get_json()
        if 'cod_empresa' not in data or 'cod_os_agenda' not in data:
            return jsonify({'status': 'error', 'message': 'Missing required parameters: cod_empresa, cod_os_agenda'}), 400
        query = f"""
            select status_agenda from os_agenda oa
            where oa.cod_empresa = {data['cod_empresa']}
            and oa.cod_os_agenda = {data['cod_os_agenda']}
        """
        # return query
        conn_oracle, cur_oracle = oracle()
        cur_oracle.execute(query)
        result = cur_oracle.fetchall()
        # return result
        if len(result) == 0:
            return jsonify({'status': 'error', 'message': 'OS Agenda not found for the given company code and OS Agenda code'}), 404
        if result[0][0] in ('E','O','F'):
            return jsonify({'status': 'error', 'message': 'Agendamento já foi encerrado'}), 400
        if result[0][0] == 'C':
            status_agenda = 'A'
        elif result[0][0] == 'A':
            status_agenda = 'C'
        else:
            status_agenda = result[0][0]
        query = f"""
            UPDATE os_agenda set status_agenda = '{status_agenda}'
            WHERE cod_empresa = {data['cod_empresa']}
            AND cod_os_agenda = {data['cod_os_agenda']}
        """
        cur_oracle.execute(query)
        conn_oracle.commit()
        cur_oracle.close()
        conn_oracle.close()
        return jsonify({'status': 'success', 'message': f'Status do agendamento atualizado'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400
    
@agendamento_bp.route('/api/agenda/os_agenda', methods=['GET'])
def get_os_agenda():
    try:
        cod_empresa = request.args.get('cod_empresa')
        cod_os_agenda = request.args.get('cod_os_agenda')
        if cod_empresa is None or cod_os_agenda is None:
            return jsonify({'status': 'error', 'message': 'Missing required parameters: cod_empresa and cod_os_agenda'}), 400
        if not cod_empresa.isdigit() or not cod_os_agenda.isdigit():
            return jsonify({'status': 'error', 'message': 'cod_empresa and cod_os_agenda must be numbers'}), 400
        query = f"""
            SELECT oa.COD_EMPRESA, oa.COD_OS_AGENDA, oa.NUMERO_OS, oa.COD_CLIENTE, TO_CHAR(oa.DATA_AGENDADA , 'YYYY-MM-DD')
            FROM OS_AGENDA oa 
            WHERE 1=1
            
                AND oa.COD_EMPRESA = {cod_empresa}
                AND oa.COD_OS_AGENDA = {cod_os_agenda}
        """
        
        conn_oracle, cur_oracle = oracle()
        cur_oracle.execute(query)
        result = cur_oracle.fetchall()
        if len(result) == 0:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'OS Agenda not found for the given company code and OS Agenda code'}), 404
        data_emissao = str(result[0][4])
        cod_os_agenda = result[0][1]
        cod_cliente = str(result[0][3])
        if not cod_cliente.isdigit():
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'Cliente não cadastrado ! corrija!'}), 400
        query = f"""
            SELECT o.DATA_EMISSAO, o.NUMERO_OS, eu.NOME_COMPLETO
            FROM OS o
            LEFT JOIN EMPRESAS_USUARIOS eu ON 1=1
                AND eu.NOME = o.nome
            WHERE 1=1
                --and o.complemento <> 'S'
                AND o.ORCAMENTO <> 'S'
                AND numero_os > 0
                AND o.COD_CLIENTE = '{cod_cliente}'
                AND o.COD_EMPRESA = {cod_empresa}
                AND o.DATA_EMISSAO >= TO_DATE('{data_emissao}', 'YYYY-MM-DD')
        """
        
        cur_oracle.execute(query)
        result = cur_oracle.fetchall()
        retorno = {}
        retorno['list_os'] = []
        for row in result:
            retorno['list_os'].append({
                'data_emissao': row[0],
                'numero_os': row[1],
                'nome_completo': row[2]
            })
        retorno['cod_empresa'] = cod_empresa
        retorno['cod_os_agenda'] = cod_os_agenda
        cur_oracle.close()
        conn_oracle.close()
        return jsonify(retorno), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@agendamento_bp.route('/api/agenda/os_agenda_public', methods=['GET'])
def get_os_agenda_public():
    try:
        cod_empresa = request.args.get('cod_empresa')
        cod_os_agenda = request.args.get('cod_os_agenda')
        if cod_empresa is None or cod_os_agenda is None:
            return jsonify({'status': 'error', 'message': 'Missing required parameters: cod_empresa and cod_os_agenda'}), 400
        if not cod_empresa.isdigit() or not cod_os_agenda.isdigit():
            return jsonify({'status': 'error', 'message': 'cod_empresa and cod_os_agenda must be numbers'}), 400
        query = f"""
            SELECT oa.COD_EMPRESA, oa.COD_OS_AGENDA, oa.NUMERO_OS, oa.COD_CLIENTE, TO_CHAR(oa.DATA_AGENDADA , 'YYYY-MM-DD')
            FROM OS_AGENDA oa 
            WHERE 1=1
            
                AND oa.COD_EMPRESA = {cod_empresa}
                AND oa.COD_OS_AGENDA = {cod_os_agenda}
        """
        conn_oracle, cur_oracle = oracle()
        cur_oracle.execute(query)
        result = cur_oracle.fetchall()
        
        if len(result) == 0:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'OS Agenda not found for the given company code and OS Agenda code'}), 404
        data_emissao = str(result[0][4])
        cod_os_agenda = result[0][1]
        query = f"""
            SELECT o.DATA_EMISSAO, o.NUMERO_OS, eu.NOME_COMPLETO
            FROM OS o
            LEFT JOIN EMPRESAS_USUARIOS eu ON 1=1
                AND eu.NOME = o.nome
            WHERE 1=1
                and o.complemento <> 'S'
                AND o.ORCAMENTO <> 'S'
                AND numero_os > 0
                AND o.COD_CLIENTE = '{str(result[0][3])}'
                AND o.COD_EMPRESA = {cod_empresa}
                AND o.DATA_EMISSAO >= TO_DATE('{data_emissao}', 'YYYY-MM-DD')
        """
        
        cur_oracle.execute(query)
        result = cur_oracle.fetchall()
        retorno = {}
        retorno['list_os'] = []
        for row in result:
            retorno['list_os'].append({
                'data_emissao': row[0],
                'numero_os': row[1],
                'nome_completo': row[2]
            })
        retorno['cod_empresa'] = cod_empresa
        retorno['cod_os_agenda'] = cod_os_agenda
        cur_oracle.close()
        conn_oracle.close()
        return jsonify(retorno), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@agendamento_bp.route('/api/agenda/change_os', methods=['POST'])
def change_os():
    try:
        data = request.get_json()
        if 'cod_empresa' not in data or 'cod_os_agenda' not in data or 'numero_os' not in data:
            return jsonify({'status': 'error', 'message': 'Missing required parameters: cod_empresa, cod_os_agenda, and numero_os'}), 400
        # chava se tudo é int
        if not isinstance(data['cod_empresa'], int) or not isinstance(data['cod_os_agenda'], int) or not isinstance(data['numero_os'], int):
            return jsonify({'status': 'error', 'message': 'cod_empresa, cod_os_agenda, and numero_os must be numbers'}), 400
        conn_oracle, cur_oracle = oracle()
        query = f"""
                UPDATE os SET cod_os_agenda = NULL
                WHERE cod_empresa = {data['cod_empresa']}
                AND cod_os_agenda = {data['cod_os_agenda']}
        """
        cur_oracle.execute(query)
        
        query = f"""
            UPDATE os_agenda SET NUMERO_OS = NULL
            WHERE 1=1
                AND COD_EMPRESA = {data['cod_empresa']}
                AND cod_os_agenda = {data['cod_os_agenda']}
        """
        cur_oracle.execute(query)
        
        query = f"""
            UPDATE os SET cod_os_agenda = {data['cod_os_agenda']}
            WHERE cod_empresa = {data['cod_empresa']}
            AND numero_os = {data['numero_os']}
        """
        cur_oracle.execute(query)
        
        query = f"""
            UPDATE os_agenda SET NUMERO_OS = {data['numero_os']}
            WHERE 1=1
                AND COD_EMPRESA = {data['cod_empresa']}
                AND cod_os_agenda = {data['cod_os_agenda']}
        """
        cur_oracle.execute(query)
        conn_oracle.commit()
        cur_oracle.close()
        conn_oracle.close()
        
        retorno = {}
        retorno['message'] = 'OS Alterada com sucesso !'
        retorno['numero_os'] = data['numero_os']
        retorno['cod_os_agenda'] = data['cod_os_agenda']
        retorno['cod_empresa'] = data['cod_empresa']
        return jsonify(retorno), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400
    