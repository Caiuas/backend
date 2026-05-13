from flask import Blueprint, jsonify, request
from database import oracle
from datetime import datetime
from auth import token_required

pecas_bp = Blueprint('pecas', __name__)

def format_date(date_value):
    if date_value is None:
        return None
    if isinstance(date_value, str):
        try:
            date_obj = datetime.strptime(date_value, '%Y-%m-%d %H:%M:%S')
            return date_obj.isoformat()
        except:
            return date_value
    elif hasattr(date_value, 'isoformat'):
        return date_value.isoformat()
    elif hasattr(date_value, 'year'):
        date_obj = datetime(date_value.year, date_value.month, date_value.day, 
                            getattr(date_value, 'hour', 0), 
                            getattr(date_value, 'minute', 0), 
                            getattr(date_value, 'second', 0))
        return date_obj.isoformat()
    else:
        return str(date_value)

@pecas_bp.route('/api/pecas/itens', methods=['GET'])
@token_required
def get_pecas_itens():
    search = request.args.get('search', '').strip().lower()
    try:
        conn_oracle, cur_oracle = oracle()
        query = """
            SELECT i.cod_item, i.DESCRICAO 
            FROM itens i
            WHERE 1=1
        """
        if search:
            query += f" AND (LOWER(i.cod_item) LIKE '%{search}%' OR LOWER(i.DESCRICAO) LIKE '%{search}%')"
        
        query += " AND ROWNUM <= 100"
        
        cur_oracle.execute(query)
        result = cur_oracle.fetchall()
        cur_oracle.close()
        conn_oracle.close()
        
        itens = []
        for row in result:
            itens.append({
                'cod_item': row[0],
                'descricao': row[1]
            })
        
        return jsonify({'itens': itens}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@pecas_bp.route('/api/pecas/ped_allparts', methods=['GET'])
@token_required
def get_pedidos():
    try:
        search = request.args.get('search', '').strip().lower()
        current_page = int(request.args.get('current_page', 1))
        limit = int(request.args.get('limit', 10))
        
        conn_oracle, cur_oracle = oracle()
        
        where_clause = "WHERE 1=1"
        if search:
            where_clause += f" AND (LOWER(numero_rm) LIKE '%{search}%' OR LOWER(quem_criou) LIKE '%{search}%' OR LOWER(status) LIKE '%{search}%' OR LOWER(carro) LIKE '%{search}%')"
            
        count_query = f"SELECT count(*) FROM caiuas_pedido_allparts {where_clause}"
        cur_oracle.execute(count_query)
        total = cur_oracle.fetchone()[0]
        
        if total == 0:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'pedidos': [], 'total': 0, 'current_page': current_page, 'total_pages': 0}), 200
            
        total_pages = (total + limit - 1) // limit
        start_row = (current_page - 1) * limit + 1
        end_row = current_page * limit

        query = f"""
            SELECT * FROM (
                SELECT t.*, ROWNUM AS rn FROM (
                    SELECT id_pedido, numero_rm, created_at, updated_at, obs, quem_criou, status, carro, cod_empresa
                    FROM caiuas_pedido_allparts
                    {where_clause}
                    ORDER BY created_at DESC
                ) t
            )
            WHERE rn BETWEEN {start_row} AND {end_row}
        """
        cur_oracle.execute(query)
        result = cur_oracle.fetchall()
        cur_oracle.close()
        conn_oracle.close()
        
        pedidos = []
        for row in result:
            pedidos.append({
                'id_pedido': row[0],
                'numero_rm': row[1],
                'created_at': format_date(row[2]),
                'updated_at': format_date(row[3]),
                'obs': row[4],
                'quem_criou': row[5],
                'status': row[6],
                'carro': row[7] if len(row) > 7 else None,
                'cod_empresa': row[8] if len(row) > 8 else None
            })
            
        return jsonify({
            'pedidos': pedidos,
            'total': total,
            'current_page': current_page,
            'total_pages': total_pages
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@pecas_bp.route('/api/pecas/ped_allparts', methods=['POST'])
@token_required
def create_pedido():
    try:
        data = request.get_json()
        numero_rm = data.get('numero_rm')
        obs = data.get('obs', '')
        carro = data.get('carro', '')
        cod_empresa = data.get('cod_empresa', None)
        
        token_data = request.token_data
        email = token_data.get('email', '').strip().lower()

        if not numero_rm:
            return jsonify({'status': 'error', 'message': 'numero_rm é obrigatório'}), 400

        conn_oracle, cur_oracle = oracle()

        query_nome = f"""
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
        cur_oracle.execute(query_nome)
        rows = cur_oracle.fetchall()
        if rows and len(rows) > 0:
            quem_criou = rows[0][1]
        else:
            quem_criou = email
        
        # Obter proximo id
        cur_oracle.execute("SELECT NVL(MAX(id_pedido), 0) + 1 FROM caiuas_pedido_allparts")
        id_pedido = cur_oracle.fetchone()[0]

        query = f"""
            INSERT INTO caiuas_pedido_allparts (id_pedido, numero_rm, created_at, updated_at, obs, quem_criou, status, carro, cod_empresa)
            VALUES ({id_pedido}, '{numero_rm}', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, '{obs}', '{quem_criou}', 'Aguardando Nota Fiscal', '{carro}', {cod_empresa if cod_empresa else 'NULL'})
        """
        cur_oracle.execute(query)
        conn_oracle.commit()
        cur_oracle.close()
        conn_oracle.close()
        
        return jsonify({'status': 'success', 'id_pedido': id_pedido}), 201
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@pecas_bp.route('/api/pecas/ped_allparts/<int:id_pedido>', methods=['GET'])
@token_required
def get_pedido(id_pedido):
    try:
        conn_oracle, cur_oracle = oracle()
        
        # Busca a capa
        query_pedido = f"""
            SELECT id_pedido, numero_rm, created_at, updated_at, obs, quem_criou, status, carro, cod_empresa
            FROM caiuas_pedido_allparts
            WHERE id_pedido = {id_pedido}
        """
        cur_oracle.execute(query_pedido)
        result = cur_oracle.fetchone()
        
        if not result:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'Pedido não encontrado'}), 404
            
        pedido = {
            'id_pedido': result[0],
            'numero_rm': result[1],
            'created_at': format_date(result[2]),
            'updated_at': format_date(result[3]),
            'obs': result[4],
            'quem_criou': result[5],
            'status': result[6],
            'carro': result[7] if len(result) > 7 else None,
            'cod_empresa': result[8] if len(result) > 8 else None
        }
        
        # Busca os itens
        query_itens = f"""
            SELECT pi.id_item, pi.id_pedido, pi.qtd, pi.cod_item, pi.updated_at, i.descricao
            FROM caiuas_pedido_allparts_item pi
            LEFT JOIN itens i ON i.cod_item = pi.cod_item
            WHERE pi.id_pedido = {id_pedido}
            ORDER BY pi.id_item ASC
        """
        cur_oracle.execute(query_itens)
        itens_result = cur_oracle.fetchall()
        
        itens = []
        for row in itens_result:
            itens.append({
                'id_item': row[0],
                'id_pedido': row[1],
                'qtd': row[2],
                'cod_item': row[3],
                'updated_at': format_date(row[4]),
                'descricao': row[5]
            })
            
        pedido['itens'] = itens
        
        cur_oracle.close()
        conn_oracle.close()
        
        return jsonify(pedido), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@pecas_bp.route('/api/pecas/ped_allparts/<int:id_pedido>', methods=['PUT'])
@token_required
def update_pedido(id_pedido):
    try:
        data = request.get_json()
        numero_rm = data.get('numero_rm')
        obs = data.get('obs')
        status = data.get('status')
        carro = data.get('carro')
        cod_empresa = data.get('cod_empresa')
        
        conn_oracle, cur_oracle = oracle()
        
        # Check if already Finalizado
        cur_oracle.execute(f"SELECT status FROM caiuas_pedido_allparts WHERE id_pedido = {id_pedido}")
        current_status = cur_oracle.fetchone()
        if current_status and current_status[0] == 'Finalizado':
            return jsonify({'status': 'error', 'message': 'Pedido finalizado não pode ser alterado.'}), 400
        
        updates = []
        if numero_rm is not None:
            updates.append(f"numero_rm = '{numero_rm}'")
        if obs is not None:
            updates.append(f"obs = '{obs}'")
        if status is not None:
            updates.append(f"status = '{status}'")
        if carro is not None:
            updates.append(f"carro = '{carro}'")
        if cod_empresa is not None:
            updates.append(f"cod_empresa = {cod_empresa if str(cod_empresa).isdigit() else 'NULL'}")
            
        if not updates:
            return jsonify({'status': 'error', 'message': 'Nenhum dado para atualizar'}), 400
            
        updates.append("updated_at = CURRENT_TIMESTAMP")
        
        query = f"UPDATE caiuas_pedido_allparts SET {', '.join(updates)} WHERE id_pedido = {id_pedido}"
        cur_oracle.execute(query)
        conn_oracle.commit()
        
        cur_oracle.close()
        conn_oracle.close()
        
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@pecas_bp.route('/api/pecas/ped_allparts/<int:id_pedido>/reabrir', methods=['POST'])
@token_required
def reabrir_pedido(id_pedido):
    try:
        conn_oracle, cur_oracle = oracle()
        
        cur_oracle.execute(f"SELECT status FROM caiuas_pedido_allparts WHERE id_pedido = {id_pedido}")
        current_status = cur_oracle.fetchone()
        if not current_status:
            return jsonify({'status': 'error', 'message': 'Pedido não encontrado.'}), 404
            
        query = f"UPDATE caiuas_pedido_allparts SET status = 'Aguardando Nota Fiscal', updated_at = CURRENT_TIMESTAMP WHERE id_pedido = {id_pedido}"
        cur_oracle.execute(query)
        conn_oracle.commit()
        
        cur_oracle.close()
        conn_oracle.close()
        
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@pecas_bp.route('/api/pecas/ped_allparts/<int:id_pedido>/itens', methods=['POST'])
@token_required
def add_item_pedido(id_pedido):
    try:
        data = request.get_json()
        cod_item = data.get('cod_item')
        qtd = data.get('qtd')
        
        if not cod_item or not qtd:
            return jsonify({'status': 'error', 'message': 'cod_item e qtd são obrigatórios'}), 400
            
        conn_oracle, cur_oracle = oracle()
        
        cur_oracle.execute(f"SELECT status FROM caiuas_pedido_allparts WHERE id_pedido = {id_pedido}")
        current_status = cur_oracle.fetchone()
        if current_status and current_status[0] == 'Finalizado':
            return jsonify({'status': 'error', 'message': 'Pedido finalizado não pode ser alterado.'}), 400
        
        
        # Verificar se item ja existe
        query_check = f"SELECT count(*) FROM caiuas_pedido_allparts_item WHERE id_pedido = {id_pedido} AND cod_item = '{cod_item}'"
        cur_oracle.execute(query_check)
        exists = cur_oracle.fetchone()[0] > 0
        if exists:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'Item já existe neste pedido. Você pode apenas alterar a quantidade.'}), 400
        
        cur_oracle.execute("SELECT NVL(MAX(id_item), 0) + 1 FROM caiuas_pedido_allparts_item")
        id_item = cur_oracle.fetchone()[0]
        
        query = f"""
            INSERT INTO caiuas_pedido_allparts_item (id_item, id_pedido, qtd, cod_item, updated_at)
            VALUES ({id_item}, {id_pedido}, {int(qtd)}, '{cod_item}', CURRENT_TIMESTAMP)
        """
        cur_oracle.execute(query)
        conn_oracle.commit()
        
        cur_oracle.close()
        conn_oracle.close()
        
        return jsonify({'status': 'success', 'id_item': id_item}), 201
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@pecas_bp.route('/api/pecas/ped_allparts/<int:id_pedido>/itens/<int:id_item>', methods=['PUT'])
@token_required
def update_item_pedido(id_pedido, id_item):
    try:
        data = request.get_json()
        qtd = data.get('qtd')
        if qtd is None:
            return jsonify({'status': 'error', 'message': 'qtd é obrigatório'}), 400
            
        conn_oracle, cur_oracle = oracle()
        
        cur_oracle.execute(f"SELECT status FROM caiuas_pedido_allparts WHERE id_pedido = {id_pedido}")
        current_status = cur_oracle.fetchone()
        if current_status and current_status[0] == 'Finalizado':
            return jsonify({'status': 'error', 'message': 'Pedido finalizado não pode ser alterado.'}), 400
            
        query = f"UPDATE caiuas_pedido_allparts_item SET qtd = {int(qtd)}, updated_at = CURRENT_TIMESTAMP WHERE id_item = {id_item} AND id_pedido = {id_pedido}"
        cur_oracle.execute(query)
        conn_oracle.commit()
        cur_oracle.close()
        conn_oracle.close()
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@pecas_bp.route('/api/pecas/ped_allparts/<int:id_pedido>/itens/<int:id_item>', methods=['DELETE'])
@token_required
def delete_item_pedido(id_pedido, id_item):
    try:
        conn_oracle, cur_oracle = oracle()
        
        cur_oracle.execute(f"SELECT status FROM caiuas_pedido_allparts WHERE id_pedido = {id_pedido}")
        current_status = cur_oracle.fetchone()
        if current_status and current_status[0] == 'Finalizado':
            return jsonify({'status': 'error', 'message': 'Pedido finalizado não pode ser alterado.'}), 400
            
        query = f"DELETE FROM caiuas_pedido_allparts_item WHERE id_item = {id_item} AND id_pedido = {id_pedido}"
        cur_oracle.execute(query)
        conn_oracle.commit()
        cur_oracle.close()
        conn_oracle.close()
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400
