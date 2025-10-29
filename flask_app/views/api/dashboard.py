from flask import Blueprint, jsonify, request
from database import oracle, chatwoot
from dotenv import load_dotenv
from datetime import datetime
load_dotenv()

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/api/dashboard/totais', methods=['GET'])
def get_totais():
    try:
        retorno = {}
        conn_oracle, cur_oracle = oracle()
        hoje = datetime.now().strftime('%Y-%m-%d')
        query = f"""
        SELECT count(*) 
                FROM os o
                WHERE 1=1
                    and trunc(o.data_emissao) >= trunc(TO_DATE('{hoje}', 'YYYY-MM-DD'))
                    and o.complemento <> 'S'
                    AND o.ORCAMENTO <> 'S'
                    AND numero_os > 0
        """
        cur_oracle.execute(query)
        result_oracle = cur_oracle.fetchall()
        retorno['total_os'] = result_oracle[0][0]
        cur_oracle.close()
        conn_oracle.close()
        return jsonify(retorno), 200
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
@dashboard_bp.route('/api/dashboard/agendamentos_des', methods=['GET'])
def get_agendamentos_des():
    try:
        conn_oracle, cur_oracle = oracle()
        query = f"""
        SELECT
            count(*)
        FROM os_agenda_servicos s
        LEFT JOIN CRM_EVENTOS ce ON 1=1
            AND ce.COD_EMPRESA = s.crm_cod_empresa
            AND ce.COD_EVENTO = s.CRM_COD_EVENTO
        LEFT JOIN OS_AGENDA oa ON 1=1
            AND oa.COD_EMPRESA = s.COD_EMPRESA
            AND oa.COD_OS_AGENDA = s.COD_OS_AGENDA
        LEFT JOIN caiuas_os_agenda_des coad ON 1=1
            AND coad.cod_empresa = oa.COD_EMPRESA 
            AND coad.cod_os_agenda = oa.cod_os_agenda
        WHERE 1=1
            AND s.data_comeca IS NOT NULL
            AND s.COD_EMPRESA IN (11,33)
            AND coad.data_envio IS null
        ORDER BY
            s.data_comeca DESC
        """
        cur_oracle.execute(query)
        result_oracle = cur_oracle.fetchall()
        agendamentos_nao_enviados = result_oracle[0][0]
        query = f"""
        SELECT
            count(*)
        FROM os_agenda_servicos s
        LEFT JOIN CRM_EVENTOS ce ON 1=1
            AND ce.COD_EMPRESA = s.crm_cod_empresa
            AND ce.COD_EVENTO = s.CRM_COD_EVENTO
        LEFT JOIN OS_AGENDA oa ON 1=1
            AND oa.COD_EMPRESA = s.COD_EMPRESA
            AND oa.COD_OS_AGENDA = s.COD_OS_AGENDA
        LEFT JOIN caiuas_os_agenda_des coad ON 1=1
            AND coad.cod_empresa = oa.COD_EMPRESA 
            AND coad.cod_os_agenda = oa.cod_os_agenda
        WHERE 1=1
            AND s.data_comeca IS NOT NULL
            AND s.COD_EMPRESA IN (11,33)
            AND coad.data_envio IS NOT NULL
        ORDER BY
            s.data_comeca DESC
        """
        cur_oracle.execute(query)
        agendamentos_enviados = cur_oracle.fetchall()[0][0]
        cur_oracle.close()
        conn_oracle.close()
        retorno = {}
        retorno['agendamentos_nao_enviados'] = agendamentos_nao_enviados
        retorno['agendamentos_enviados'] = agendamentos_enviados
        retorno['total_agendamentos'] = agendamentos_nao_enviados + agendamentos_enviados
        return jsonify(retorno), 200
    except Exception as e:
        try:
            cur_oracle.close()
            conn_oracle.close()
        except:
            pass
        return jsonify({'status': 'error', 'message': str(e)}), 500
    