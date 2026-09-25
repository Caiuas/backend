from flask import Blueprint, jsonify, request
from database import oracle, chatwoot
from dotenv import load_dotenv
from datetime import datetime
from auth import token_required
load_dotenv()

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/api/dashboard', methods=['GET'])
@token_required
def get_dashboard():
    cur_oracle = None
    conn_oracle = None
    try:
        token_data = request.token_data
        email = token_data.get('email').strip().lower()

        ano_mes = (request.args.get('ano_mes') or '').strip()
        if not ano_mes:
            return jsonify({'status': 'error', 'message': 'ano_mes é obrigatório (formato YYYY-MM)'}), 400
        try:
            referencia = datetime.strptime(ano_mes, '%Y-%m')
        except ValueError:
            return jsonify({'status': 'error', 'message': 'ano_mes inválido. Use o formato YYYY-MM'}), 400

        start_month = referencia.month - 2
        start_year = referencia.year
        while start_month <= 0:
            start_month += 12
            start_year -= 1
        data_inicial = f'{start_year:04d}-{start_month:02d}-01'

        end_month = referencia.month + 1
        end_year = referencia.year
        if end_month > 12:
            end_month = 1
            end_year += 1
        data_final = f'{end_year:04d}-{end_month:02d}-01'

        conn_oracle, cur_oracle = oracle()

        query = f"""
            SELECT saf.COD_ACESSO
            FROM empresas_usuarios eu
            LEFT JOIN SISTEMA_ACESSO_FUNCAO saf ON 1=1
                AND saf.COD_FUNCAO = eu.COD_FUNCAO
            WHERE eu.DEMITIDO <> 'S'
                AND lower(eu.EMAIL) = '{email}'
                AND saf.COD_ACESSO = '50190'
            GROUP BY saf.COD_ACESSO
        """
        cur_oracle.execute(query)
        possui_acesso_total = cur_oracle.fetchone() is not None

        if possui_acesso_total:
            tipo_dashboard = 'gerente'
            filtro_vendedor = ''
        else:
            tipo_dashboard = 'vendedor'
            query_nome = f"""
                SELECT eu.nome
                FROM empresas_usuarios eu
                LEFT JOIN SISTEMA_ACESSO_FUNCAO saf ON 1=1
                    AND saf.COD_FUNCAO = eu.COD_FUNCAO
                WHERE eu.DEMITIDO <> 'S'
                    AND lower(eu.EMAIL) = '{email}'
                GROUP BY eu.COD_EMPRESA, eu.nome
                ORDER BY eu.cod_empresa
            """
            cur_oracle.execute(query_nome)
            usuarios = [row[0] for row in cur_oracle.fetchall()]

            if not usuarios:
                cur_oracle.close()
                conn_oracle.close()
                return jsonify({'status': 'error', 'message': 'Usuário não encontrado'}), 400

            vendedores = ', '.join(f"'{usuario}'" for usuario in usuarios)
            filtro_vendedor = f"AND vp.VENDEDOR IN ({vendedores})"

        query = f"""
            SELECT TO_CHAR(vp.DATA_VENDA, 'YYYY-MM') AS ano_mes,
                   COUNT(DISTINCT v.CHASSI_COMPLETO) AS total
            FROM veiculos v
            LEFT JOIN VEICULOS_PROPOSTAS vp ON 1=1
                AND vp.CHASSI_RESUMIDO = v.CHASSI_RESUMIDO
                AND vp.STATUS_PROPOSTA <> 'C'
            WHERE v.status = 'V'
                AND vp.DATA_VENDA >= TO_DATE('{data_inicial}', 'YYYY-MM-DD')
                AND vp.DATA_VENDA < TO_DATE('{data_final}', 'YYYY-MM-DD')
                AND TO_CHAR(v.cod_cliente) <> '22534303000127'
                {filtro_vendedor}
            GROUP BY TO_CHAR(vp.DATA_VENDA, 'YYYY-MM')
            ORDER BY ano_mes
        """
        cur_oracle.execute(query)
        rows = cur_oracle.fetchall()

        query = f"""
            SELECT COUNT(*)
            FROM VEICULOS_PROPOSTAS vp
            LEFT JOIN caiuas_veic_proc cvp ON 1=1
                AND cvp.cod_proposta = vp.cod_proposta
            WHERE vp.STATUS_PROPOSTA NOT IN ('C','V')
                AND TRUNC(vp.EMISSAO) >= TO_DATE('2024-01-01', 'YYYY-MM-DD')
                AND (cvp.REPASSE IS NULL OR cvp.REPASSE <> 'S')
                {filtro_vendedor}
        """
        cur_oracle.execute(query)
        aguardando_faturamento = cur_oracle.fetchone()[0]

        cur_oracle.close()
        conn_oracle.close()

        totais_mes = {row[0]: row[1] for row in rows}

        meses = []
        total = 0
        m = start_year
        mes = start_month
        for _ in range(3):
            chave = f'{m:04d}-{mes:02d}'
            qtd = totais_mes.get(chave, 0)
            total += qtd
            meses.append({'ano_mes': chave, 'total': qtd})
            mes += 1
            if mes > 12:
                mes = 1
                m += 1

        return jsonify({
            'tipo_dashboard': tipo_dashboard,
            'ano_mes': ano_mes,
            'faturados_ultimos_3_meses': total,
            'aguardando_faturamento': aguardando_faturamento,
            'meses': meses
        }), 200
    except Exception as e:
        try:
            if cur_oracle:
                cur_oracle.close()
            if conn_oracle:
                conn_oracle.close()
        except:
            pass
        return jsonify({'status': 'error', 'message': str(e)}), 500

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
    