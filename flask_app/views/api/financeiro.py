from flask import Blueprint, jsonify, request
from database import oracle, chatwoot
from dotenv import load_dotenv
from datetime import datetime
from auth import token_required
import re
load_dotenv()

financeiro_bp = Blueprint('financeiro', __name__)

@financeiro_bp.route('/api/financeiro/lcontas', methods=['GET'])
@token_required
def get_financeiro_lcontas():
    try:
        token_data = request.token_data
        email = token_data['email']
        cod_conta_corrente = request.args.get('cod_conta_corrente', None)
        initial_date = request.args.get('initial_date', None)
        final_date = request.args.get('final_date', None)
        current_page = int(request.args.get('current_page', 1))
        search = request.args.get('search', None)
        limit = int(request.args.get('limit', 10))
        retorno = {}
        if not initial_date or not final_date:
            # initial_date e final_date é primeiro e ultimo dia do mês atual
            initial_date = datetime.now().replace(day=1).strftime('%Y-%m-%d')
            final_date = datetime.now().strftime('%Y-%m-%d')
            # return jsonify({'status': 'error', 'message': 'Initial date and final date are required.'}), 400
        
        # checa se initial_date e final_date estão no formato correto YYYY-MM-DD
        date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')
        if not date_pattern.match(initial_date) or not date_pattern.match(final_date):
            return jsonify({'status': 'error', 'message': 'Dates must be in YYYY-MM-DD format.'}), 400
        
        conn_oracle, cur_oracle = oracle()
        query = f"""
                SELECT count(*)
                FROM lcontas lc
                LEFT JOIN conta_corrente cc ON 1=1
                    AND lc.COD_CONTA_CORRENTE = cc.COD_CONTA_CORRENTE  
                    AND lc.COD_EMPRESA = cc.COD_EMPRESA 
                LEFT JOIN empresas e ON 1=1
                    AND e.COD_EMPRESA = lc.COD_EMPRESA 
                LEFT JOIN usuario_conta_corrente ucc ON 1=1
                    AND ucc.COD_EMPRESA = lc.COD_EMPRESA 
                    AND ucc.USUARIO = lc.NOME 
                    AND ucc.COD_CONTA_CORRENTE = lc.COD_CONTA_CORRENTE 
                LEFT JOIN EMPRESAS_USUARIOS eu ON 1=1
                    AND ucc.USUARIO = eu.NOME 
                LEFT JOIN origem_lancamento ol ON 1=1
                    AND ol.COD_ORIGEM_LANC = lc.COD_ORIGEM_LANC 
                WHERE 1=1
                    --AND lc.COD_CONTA_CORRENTE NOT IN (2,3)
                    AND trunc(lc."DATA") BETWEEN TO_DATE('{initial_date}', 'YYYY-MM-DD') AND TO_DATE('{final_date}', 'YYYY-MM-DD')
                    AND (lc.COD_EMPRESA, lc.COD_CONTA_CORRENTE) IN (
                        SELECT ucc.COD_EMPRESA, ucc.COD_CONTA_CORRENTE 
                        FROM usuario_conta_corrente ucc
                        LEFT JOIN EMPRESAS_USUARIOS eu ON ucc.USUARIO = eu.NOME 
                        WHERE lower(eu.email) = '{email.lower()}'
                    )
                    ORDER BY lc.COD_CONTA_CORRENTE, lc."DATA"  DESC
        """
        cur_oracle.execute(query)
        total = cur_oracle.fetchone()[0]
        
        if total == 0:
            retorno['message'] = 'Nenhum lançamento encontrado para os filtros informados.'
            return jsonify(retorno), 200
        
        offset = (current_page - 1) * limit
        total_pages = (total + limit - 1) // limit
        start_row = (current_page - 1) * limit + 1
        end_row = current_page * limit
        
        if current_page > total_pages:
            return jsonify({'status': 'error', 'message': 'Página inválida'}), 400
        
        query = f"""
        
            SELECT *
                FROM (
                    SELECT t.*, ROWNUM AS rn
                    FROM (
                SELECT lc.COD_EMPRESA,
                    lc.COD_ORIGEM_LANC ,
                    e.NOME NOME_EMPRESA,
                    lc.COD_CONTA_CORRENTE ccc,
                    ol.DESCRICAO,
                    cc.descricao nome_conta, 
                    TO_CHAR(lc."DATA", 'YYYY-MM-DD"T"HH24:MI:SS') AS DATA_LANCAMENTO,
                    lc.lanc NUM_LANCAMENTO,
                    lc.nome RESPONSAVEL,
                    lc.VALOR,
                    lc.db_cr,
                    concat(lc.historico,lc.HISTORICO1) historico,
                    cc.num_conta
                FROM lcontas lc
                LEFT JOIN conta_corrente cc ON 1=1
                    AND lc.COD_CONTA_CORRENTE = cc.COD_CONTA_CORRENTE  
                    AND lc.COD_EMPRESA = cc.COD_EMPRESA 
                LEFT JOIN empresas e ON 1=1
                    AND e.COD_EMPRESA = lc.COD_EMPRESA 
                LEFT JOIN usuario_conta_corrente ucc ON 1=1
                    AND ucc.COD_EMPRESA = lc.COD_EMPRESA 
                    AND ucc.USUARIO = lc.NOME 
                    AND ucc.COD_CONTA_CORRENTE = lc.COD_CONTA_CORRENTE 
                LEFT JOIN EMPRESAS_USUARIOS eu ON 1=1
                    AND ucc.USUARIO = eu.NOME 
                LEFT JOIN origem_lancamento ol ON 1=1
                    AND ol.COD_ORIGEM_LANC = lc.COD_ORIGEM_LANC 
                WHERE 1=1
                    --AND lc.COD_CONTA_CORRENTE NOT IN (2,3)
                    AND lc.COD_CONTA_CORRENTE NOT IN (2)
                    AND trunc(lc."DATA") BETWEEN TO_DATE('{initial_date}', 'YYYY-MM-DD') AND TO_DATE('{final_date}', 'YYYY-MM-DD')
                    AND (lc.COD_EMPRESA, lc.COD_CONTA_CORRENTE) IN (
                        SELECT ucc.COD_EMPRESA, ucc.COD_CONTA_CORRENTE 
                        FROM usuario_conta_corrente ucc
                        LEFT JOIN EMPRESAS_USUARIOS eu ON ucc.USUARIO = eu.NOME 
                        WHERE lower(eu.email) = '{email.lower()}'
                    )
                    ORDER BY lc.COD_CONTA_CORRENTE, lc."DATA"  DESC, lc.lanc
            ) t
                )
                WHERE
                    rn BETWEEN {start_row} AND {end_row}
        """
        cur_oracle.execute(query)
        rows = cur_oracle.fetchall()
        retorno['lancamentos'] = []
        for row in rows:
            if row[6]:  # data_lancamento
                try:
                    data_lancamento_obj = datetime.strptime(row[6], '%Y-%m-%d %H:%M:%S')
                    data_lancamento_iso = data_lancamento_obj.isoformat()
                except:
                    data_lancamento_iso = row[6]  # fallback para string original
            else:
                data_lancamento_iso = None
            lancamento = {
                'cod_empresa': row[0],
                'cod_origem_lanc': row[1],
                'nome_empresa': row[2],
                'cod_conta_corrente': row[3],
                'descricao_origem': row[4],
                'nome_conta': row[5],
                'data_lancamento': data_lancamento_iso,
                'num_lancamento': row[7],
                'responsavel': row[8],
                'valor': float(row[9]),
                'db_cr': row[10],
                'historico': row[11],
                'num_conta': row[12]
            }
            retorno['lancamentos'].append(lancamento)
        retorno['current_page'] = current_page
        retorno['total_pages'] = total_pages
        retorno['total_items'] = total
        retorno['initial_date'] = initial_date
        retorno['final_date'] = final_date
        return jsonify(retorno), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    