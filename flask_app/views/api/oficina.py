from flask import Blueprint, jsonify, request
from database import oracle, chatwoot
from dotenv import load_dotenv
from datetime import datetime
from auth import token_required
load_dotenv()

oficina_bp = Blueprint('oficina', __name__)

@oficina_bp.route('/api/oficina/list_os', methods=['GET'])
@token_required
def get_oficina_list_os():
    try:
        search = request.args.get('search', None)
        token_data = request.token_data
        email = token_data.get('email').strip().lower()
        status = request.args.get('status', None)
        tipo_evento = request.args.get('tipo_evento', None)
        initial_date = request.args.get('initial_date', None)
        final_date = request.args.get('final_date', None)
        current_page = int(request.args.get('current_page', 1))
        search = request.args.get('search', None)
        limit = int(request.args.get('limit', 100))
        retorno = {}

        query_search = ""
        if search:
            query_search = f" AND lower(o.numero_os) LIKE ('%{search.lower()}%') "
            
        filter_initial_date = ''
        filter_final_date = ''
        if initial_date:
            try:
                datetime.strptime(initial_date, '%Y-%m-%d')
                filter_initial_date = f" AND TRUNC(o.DATA_EMISSAO) >= TO_DATE('{initial_date}', 'YYYY-MM-DD') "
            except ValueError:
                return jsonify({'status': 'error', 'message': 'Data inicial inválida. Use o formato YYYY-MM-DD'}), 400
        
        if final_date:
            try:
                datetime.strptime(final_date, '%Y-%m-%d')
                filter_final_date = f" AND TRUNC(o.DATA_EMISSAO) <= TO_DATE('{final_date}', 'YYYY-MM-DD')"
            except ValueError:
                return jsonify({'status': 'error', 'message': 'Data final inválida. Use o formato YYYY-MM-DD'}), 400
        
        query = f"""
        select count(*)
        FROM os o
        LEFT JOIN clientes c ON 1=1
        	AND c.COD_CLIENTE = o.COD_CLIENTE 
        LEFT JOIN produtos_modelos pm ON 1=1
        	AND pm.COD_PRODUTO = o.COD_PRODUTO 
        	AND pm.COD_MODELO = o.COD_MODELO 
        LEFT JOIN produtos p ON 1=1
        	AND p.COD_PRODUTO = pm.COD_PRODUTO 
        WHERE 1=1
            {query_search}
            {filter_initial_date}
            {filter_final_date}
        """
        
        conn_oracle, cur_oracle = oracle()
        cur_oracle.execute(query)
        total = cur_oracle.fetchone()[0]
        if total == 0:
            try:
                cur_oracle.close()
                conn_oracle.close()
            except:
                pass
            return jsonify({'status': 'error', 'message': 'Não há reclamações com o filtro'}), 404
        
        offset = (current_page - 1) * limit
        total_pages = (total + limit - 1) // limit
        start_row = (current_page - 1) * limit + 1
        end_row = current_page * limit
        
        if current_page > total_pages:
            try:
                cur_oracle.close()
                conn_oracle.close()
            except:
                pass
            return jsonify({'status': 'error', 'message': 'Página não encontrada'}), 404
        
        query = f"""
                SELECT *
                FROM (
                    SELECT t.*, ROWNUM AS rn
                    FROM (
                        -- Sua query original com ORDER BY aqui dentro
                        SELECT o.COD_EMPRESA, 
                        o.numero_os, 
                        o.STATUS_OS, 
                        TO_CHAR(o.DATA_EMISSAO, 'YYYY-MM-DD HH24:MI:SS') AS DATA_EMISSAO,
                        o.CONSULTOR_RECEPCAO , o.COD_PRODUTO, o.COD_MODELO, c.COD_CLIENTE, c.NOME, pm.DESCRICAO_MODELO, p.DESCRICAO_PRODUTO 
                        FROM os o
                        LEFT JOIN clientes c ON 1=1
                            AND c.COD_CLIENTE = o.COD_CLIENTE 
                        LEFT JOIN produtos_modelos pm ON 1=1
                            AND pm.COD_PRODUTO = o.COD_PRODUTO 
                            AND pm.COD_MODELO = o.COD_MODELO 
                        LEFT JOIN produtos p ON 1=1
                            AND p.COD_PRODUTO = pm.COD_PRODUTO 
                        WHERE 1=1
                            {query_search}
                            {filter_initial_date}
                            {filter_final_date}
                        ORDER BY o.DATA_EMISSAO desc
                    ) t 
                )
                WHERE 
                    rn BETWEEN {start_row} AND {end_row}
        """
        
        cur_oracle.execute(query)
        rows = cur_oracle.fetchall()
        retorno['current_page'] = current_page
        retorno['total_pages'] = total_pages
        retorno['total_items'] = total
        retorno['os'] = []
        for row in rows:
            if row[3]:  # data_emissao
                try:
                    data_emissao_obj = datetime.strptime(row[3], '%Y-%m-%d %H:%M:%S')
                    data_emissao_iso = data_emissao_obj.isoformat()
                except:
                    data_emissao_iso = row[3]  # fallback para string original
            else:
                data_emissao_iso = None
            retorno['os'].append({
                'cod_empresa': row[0],
                'numero_os': row[1],
                'status_os': row[2],
                'data_emissao': data_emissao_iso,
                'consultor_recepcao': row[4],
                'cod_produto': row[5],
                'cod_modelo': row[6],
                'cod_cliente': row[7],
                'nome_cliente': row[8],
                'descricao_modelo': row[9],
                'descricao_produto': row[10],
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
        return jsonify({'status': 'error', 'message': str(e)}), 400

