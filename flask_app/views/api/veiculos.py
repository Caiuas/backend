from flask import Blueprint, jsonify, request
from database import oracle, chatwoot
from dotenv import load_dotenv
from datetime import datetime
from auth import token_required
load_dotenv()

veiculos_bp = Blueprint('veiculos', __name__)

@veiculos_bp.route('/api/veiculos/estoque', methods=['GET'])
def get_veiculos_estoque():
    try:
        query = f"""
            SELECT 
                vp.COD_PROPOSTA, 
                vp.EMISSAO data_proposta, 
                vp.VENDEDOR cod_vendedor, 
                eu.NOME_COMPLETO nome_vendedor, 
                pm.DESCRICAO_MODELO modelo, 
                ce.DESCRICAO cor, 
                v.ANO_MODELO, 
                v.CHASSI_COMPLETO, 
                e.NOME empresa, 
                v.DATA_NOTA emissao,
                p.DESCRICAO patio,
                c.COD_CLIENTE, 
                c.NOME nome_cliente,
                CASE 
                    WHEN v.novo_usado = 'U' THEN 'Usado'
                    ELSE
                        'Novo'
                END novo_usado
            FROM veiculos v 
            LEFT JOIN produtos pr ON 1=1
                AND pr.COD_PRODUTO = v.COD_PRODUTO 
            LEFT JOIN CORES_EXTERNAS ce ON 1=1
                AND ce.COR_EXTERNA = v.COR_EXTERNA 
            LEFT JOIN produtos_modelos pm ON 1=1
                AND pm.COD_PRODUTO = v.COD_PRODUTO 
                AND pm.COD_MODELO = v.COD_MODELO 
            LEFT JOIN VEICULOS_PROPOSTAS vp ON 1=1
                --AND vp.COD_PROPOSTA = v.COD_PROPOSTA OR vp.COD_PROPOSTA = v.COD_PROPOSTA_INTERNET 
                AND vp.CHASSI_RESUMIDO = v.CHASSI_RESUMIDO 
                AND vp.STATUS_PROPOSTA <> 'C'
            LEFT JOIN clientes c ON c.COD_CLIENTE = vp.COD_CLIENTE 
            LEFT JOIN patio p ON 1=1
                AND p.COD_PATIO = v.COD_PATIO
            LEFT JOIN EMPRESAS_USUARIOS eu ON 1=1
                AND eu.NOME = vp.VENDEDOR 
            LEFT JOIN empresas_usuarios eu2 ON 1=1
                AND eu2.nome = vp.QUEM_APROVOU 
            LEFT JOIN empresas e ON 1=1
                AND e.cod_empresa = v.COD_EMPRESA 
            WHERE v.status = 'E'
            ORDER BY pm.DESCRICAO_MODELO
        """
        conn_oracle, cur_oracle = oracle()
        cur_oracle.execute(query)
        result = cur_oracle.fetchall()
        cur_oracle.close()
        conn_oracle.close()
        retorno = {}
        retorno['veiculos'] = []
        for row in result:
            def format_date(date_value):
                if date_value is None:
                    return None
                if isinstance(date_value, str):
                    try:
                        # Se já é string, tenta converter para datetime primeiro
                        date_obj = datetime.strptime(date_value, '%Y-%m-%d %H:%M:%S')
                        return date_obj.isoformat()
                    except:
                        # Se não conseguir converter, retorna a string original
                        return date_value
                elif hasattr(date_value, 'isoformat'):
                    # Se é um objeto datetime, usa isoformat
                    return date_value.isoformat()
                elif hasattr(date_value, 'year'):
                    # Se é um objeto de data do Oracle, converte para datetime
                    date_obj = datetime(date_value.year, date_value.month, date_value.day, 
                                      getattr(date_value, 'hour', 0), 
                                      getattr(date_value, 'minute', 0), 
                                      getattr(date_value, 'second', 0))
                    return date_obj.isoformat()
                else:
                    return str(date_value)
            veiculo = {
                'cod_proposta': row[0] if row[0] != 0 else None,
                'data_proposta': format_date(row[1]),
                'cod_vendedor': row[2],
                'nome_vendedor': row[3],
                'modelo': row[4],
                'cor': row[5],
                'ano_modelo': row[6],
                'chassi_completo': row[7],
                'empresa': row[8],
                'emissao': format_date(row[9]),
                'patio': row[10],
                'cod_cliente': row[11],
                'nome_cliente': row[12],
                'novo_usado': row[13]
            }
            retorno['veiculos'].append(veiculo)
        return jsonify(retorno), 200

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@veiculos_bp.route('/api/veiculos/aguardando_faturamento', methods=['GET'])
def get_veiculos_aguardando_faturamento():
    try:
        query = f"""
            SELECT 
                v.COD_PROPOSTA, 
                vp.EMISSAO data_proposta, 
                vp.VENDEDOR cod_vendedor, 
                eu.NOME_COMPLETO nome_vendedor, 
                pm.DESCRICAO_MODELO modelo, 
                ce.DESCRICAO cor, 
                v.ANO_MODELO, 
                v.CHASSI_COMPLETO, 
                e.NOME empresa, 
                v.DATA_NOTA emissao,
                p.DESCRICAO patio,
                c.COD_CLIENTE, 
                c.NOME nome_cliente,
                CASE 
                    WHEN v.novo_usado = 'U' THEN 'Usado'
                    ELSE
                        'Novo'
                END novo_usado,
                CASE
                    WHEN c.COD_CID_COM <> NULL THEN cid_com.DESCRICAO
                    WHEN c.COD_CID_RES <> NULL THEN cid_res.DESCRICAO 
                    ELSE cid_cob.DESCRICAO 
                END cidade
            FROM veiculos v 
            LEFT JOIN produtos pr ON 1=1
                AND pr.COD_PRODUTO = v.COD_PRODUTO 
            LEFT JOIN CORES_EXTERNAS ce ON 1=1
                AND ce.COR_EXTERNA = v.COR_EXTERNA 
            LEFT JOIN produtos_modelos pm ON 1=1
                AND pm.COD_PRODUTO = v.COD_PRODUTO 
                AND pm.COD_MODELO = v.COD_MODELO 
            LEFT JOIN VEICULOS_PROPOSTAS vp ON 1=1
                --AND vp.COD_PROPOSTA = v.COD_PROPOSTA OR vp.COD_PROPOSTA = v.COD_PROPOSTA_INTERNET 
                AND vp.CHASSI_RESUMIDO = v.CHASSI_RESUMIDO 
                AND vp.STATUS_PROPOSTA <> 'C'
            LEFT JOIN clientes c ON c.COD_CLIENTE = vp.COD_CLIENTE 
            LEFT JOIN patio p ON 1=1
                AND p.COD_PATIO = v.COD_PATIO
            LEFT JOIN EMPRESAS_USUARIOS eu ON 1=1
                AND eu.NOME = vp.VENDEDOR 
            LEFT JOIN empresas_usuarios eu2 ON 1=1
                AND eu2.nome = vp.QUEM_APROVOU 
            LEFT JOIN empresas e ON 1=1
                AND e.cod_empresa = v.COD_EMPRESA 
            LEFT JOIN cidades cid_res ON 1=1
                AND cid_res.cod_cidades = c.COD_CID_RES 
                AND cid_res.uf = c.UF_RES 
            LEFT JOIN cidades cid_com ON 1=1
                AND cid_com.cod_cidades = c.COD_CID_COM 
                AND cid_com.uf = c.UF_COM 
            LEFT JOIN cidades cid_cob ON 1=1
                AND cid_cob.cod_cidades = c.COD_CID_COBRANCA  
                AND cid_cob.uf = c.UF_COBRANCA 
            WHERE v.status = 'E'
                AND v.cod_proposta <> 0
                AND v.cod_proposta IS NOT null
            ORDER BY pm.DESCRICAO_MODELO
        """
        conn_oracle, cur_oracle = oracle()
        cur_oracle.execute(query)
        result = cur_oracle.fetchall()
        
        retorno = {}
        retorno['veiculos'] = []
        for row in result:
            def format_date(date_value):
                if date_value is None:
                    return None
                if isinstance(date_value, str):
                    try:
                        # Se já é string, tenta converter para datetime primeiro
                        date_obj = datetime.strptime(date_value, '%Y-%m-%d %H:%M:%S')
                        return date_obj.isoformat()
                    except:
                        # Se não conseguir converter, retorna a string original
                        return date_value
                elif hasattr(date_value, 'isoformat'):
                    # Se é um objeto datetime, usa isoformat
                    return date_value.isoformat()
                elif hasattr(date_value, 'year'):
                    # Se é um objeto de data do Oracle, converte para datetime
                    date_obj = datetime(date_value.year, date_value.month, date_value.day, 
                                      getattr(date_value, 'hour', 0), 
                                      getattr(date_value, 'minute', 0), 
                                      getattr(date_value, 'second', 0))
                    return date_obj.isoformat()
                else:
                    return str(date_value)
            veiculo = {
                'cod_proposta': row[0] if row[0] != 0 else None,
                'data_proposta': format_date(row[1]),
                'cod_vendedor': row[2],
                'nome_vendedor': row[3],
                'modelo': row[4],
                'cor': row[5],
                'ano_modelo': row[6],
                'chassi_completo': row[7],
                'empresa': row[8],
                'emissao': format_date(row[9]),
                'patio': row[10],
                'cod_cliente': row[11],
                'nome_cliente': row[12],
                'novo_usado': row[13],
                'cidade': row[14],
                'andamento': None,
                'usado': None
            }
            query = f"""
            SELECT cav.DESCRICAO  FROM CAIUAS_ANDAMENTO_VEICULO cav
                WHERE chassi_completo = '{veiculo["chassi_completo"]}'
                AND created_at = (SELECT max(created_at) FROM CAIUAS_ANDAMENTO_VEICULO cav
                WHERE chassi_completo = '{veiculo["chassi_completo"]}')
                ORDER BY created_at DESC
            """
            cur_oracle.execute(query)
            andamento_result = cur_oracle.fetchone()
            if andamento_result:
                veiculo['andamento'] = andamento_result[0]
            
            query = f"""
                SELECT count(*) FROM VEIC_FORMAS_PAGAMENTO vfp
                LEFT JOIN FORMA_PGTO fp ON 1=1
                    AND fp.cod_empresa = vfp.COD_EMPRESA 
                    AND fp.COD_FORMA_PGTO = vfp.COD_FORMA_PGTO 
                WHERE 1=1
                    AND vfp.cod_proposta = '{veiculo["cod_proposta"]}'
                    AND lower(descricao) LIKE ('%usado%')
            """
            cur_oracle.execute(query)
            usado_result = cur_oracle.fetchone()
            if usado_result and usado_result[0] > 0:
                veiculo['usado'] = True
            
            retorno['veiculos'].append(veiculo)
        cur_oracle.close()
        conn_oracle.close()
        return jsonify(retorno), 200

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@veiculos_bp.route('/api/veiculos/muda_andamento_veiculo', methods=['POST'])
@token_required
def veiculos_muda_andamento_veiculo():
    try:
        data = request.get_json()
        token_data = request.token_data
        email = token_data.get('email').strip().lower()
        chassi_completo = data.get('chassi_completo')
        andamento = data.get('andamento', None)
        if not chassi_completo or not andamento:
            return jsonify({'status': 'error', 'message': 'Chassi completo e andamento são obrigatórios'}), 400
        query = f"""
            select count(*) from veiculos where chassi_completo = '{chassi_completo}'
        """
        conn_oracle, cur_oracle = oracle()
        cur_oracle.execute(query)
        result = cur_oracle.fetchone()
        if result[0] == 0:
            return jsonify({'status': 'error', 'message': 'Chassi não encontrado'}), 400
        query = f"""
        INSERT INTO caiuas_andamento_veiculo (id_andamento_veiculo, chassi_completo, created_at, descricao, quem_criou)
            VALUES (seq_caiuas_andamento_veiculo.NEXTVAL, '{chassi_completo}', CURRENT_TIMESTAMP, '{andamento}','{email}')
            """
        cur_oracle.execute(query)
        conn_oracle.commit()
        cur_oracle.close()
        conn_oracle.close()
        return jsonify({'status': 'success', 'message': 'Andamento atualizado com sucesso'}), 200
    except Exception as e:
        try:
            cur_oracle.close()
            conn_oracle.close()
        except:
            pass
        return jsonify({'status': 'error', 'message': str(e)}), 400
    
@veiculos_bp.route('/api/veiculos/faturados', methods=['GET'])
@token_required
def veiculos_faturados():
    try:
        initial_date = request.args.get('initial_date')
        final_date = request.args.get('final_date')
        token_data = request.token_data
        email = token_data.get('email').strip().lower()
        if not initial_date or not final_date:
            return jsonify({'status': 'error', 'message': 'Datas inicial e final são obrigatórias'}), 400
        
        # valida data inicial e final e veja se estao no formato correto
        try:
            initial_date_obj = datetime.strptime(initial_date, '%Y-%m-%d')
            final_date_obj = datetime.strptime(final_date, '%Y-%m-%d')
        except ValueError:
            return jsonify({'status': 'error', 'message': 'Datas inválidas. Use o formato YYYY-MM-DD'}), 400

        query = f"""
            SELECT saf.COD_ACESSO 
            FROM empresas_usuarios eu
            LEFT JOIN SISTEMA_ACESSO_FUNCAO saf ON 1=1
                AND saf.COD_FUNCAO = eu.COD_FUNCAO 
            WHERE 1=1
                AND eu.DEMITIDO <> 'S'
                AND lower(eu.EMAIl) = '{email}'
                AND saf.COD_ACESSO = '50113'
            GROUP BY saf.COD_ACESSO
        """
        conn_oracle, cur_oracle = oracle()
        cur_oracle.execute(query)
        rows = cur_oracle.fetchall()
        if len(rows) == 0:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'Usuário não autorizado - 50113'}), 403
        query = f"""
            SELECT 
                v.COD_PROPOSTA, 
                vp.EMISSAO data_proposta, 
                vp.VENDEDOR cod_vendedor, 
                eu.NOME_COMPLETO nome_vendedor, 
                pm.DESCRICAO_MODELO modelo, 
                ce.DESCRICAO cor, 
                v.ANO_MODELO, 
                v.CHASSI_COMPLETO, 
                e.NOME empresa, 
                v.DATA_NOTA emissao,
                p.DESCRICAO patio,
                c.COD_CLIENTE, 
                c.NOME nome_cliente,
                CASE 
                    WHEN v.novo_usado = 'U' THEN 'Usado'
                    WHEN v.COD_PROPOSTA_INTERNET IS NOT NULL THEN 'Direta'
                    ELSE
                        'Novo'
                END novo_usado,
                cf.PLACA,
                CASE
                    WHEN c.COD_CID_COM <> NULL THEN cid_com.DESCRICAO
                    WHEN c.COD_CID_RES <> NULL THEN cid_res.DESCRICAO 
                    ELSE cid_cob.DESCRICAO 
                END cidade
            FROM veiculos v 
            LEFT JOIN produtos pr ON 1=1
                AND pr.COD_PRODUTO = v.COD_PRODUTO 
            LEFT JOIN CORES_EXTERNAS ce ON 1=1
                AND ce.COR_EXTERNA = v.COR_EXTERNA 
            LEFT JOIN produtos_modelos pm ON 1=1
                AND pm.COD_PRODUTO = v.COD_PRODUTO 
                AND pm.COD_MODELO = v.COD_MODELO 
            LEFT JOIN VEICULOS_PROPOSTAS vp ON 1=1
                --AND vp.COD_PROPOSTA = v.COD_PROPOSTA OR vp.COD_PROPOSTA = v.COD_PROPOSTA_INTERNET 
                AND vp.CHASSI_RESUMIDO = v.CHASSI_RESUMIDO 
                AND vp.STATUS_PROPOSTA <> 'C'
            LEFT JOIN clientes c ON c.COD_CLIENTE = vp.COD_CLIENTE 
            LEFT JOIN patio p ON 1=1
                AND p.COD_PATIO = v.COD_PATIO
            LEFT JOIN EMPRESAS_USUARIOS eu ON 1=1
                AND eu.NOME = vp.VENDEDOR 
            LEFT JOIN empresas_usuarios eu2 ON 1=1
                AND eu2.nome = vp.QUEM_APROVOU 
            LEFT JOIN empresas e ON 1=1
                AND e.cod_empresa = v.COD_EMPRESA
            LEFT JOIN CLIENTES_FROTA cf ON 1=1
                AND cf.chassi = v.CHASSI_COMPLETO 
                AND cf.COD_CLIENTE = c.COD_CLIENTE  
                AND cf.nome = vp.VENDEDOR 
            LEFT JOIN cidades cid_res ON 1=1
                AND cid_res.cod_cidades = c.COD_CID_RES 
                AND cid_res.uf = c.UF_RES 
            LEFT JOIN cidades cid_com ON 1=1
                AND cid_com.cod_cidades = c.COD_CID_COM 
                AND cid_com.uf = c.UF_COM 
            LEFT JOIN cidades cid_cob ON 1=1
                AND cid_cob.cod_cidades = c.COD_CID_COBRANCA  
                AND cid_cob.uf = c.UF_COBRANCA 
            WHERE v.status = 'V'
                and v.cod_cliente <> '22534303000127'
                AND TRUNC(vp.DATA_VENDA) BETWEEN TO_DATE('{initial_date}', 'YYYY-MM-DD') AND TO_DATE('{final_date}', 'YYYY-MM-DD')
            ORDER BY pm.DESCRICAO_MODELO
        """
        cur_oracle.execute(query)
        result = cur_oracle.fetchall()
        if len(result) == 0:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'success', 'veiculos': []}), 404
        retorno = {}
        retorno['veiculos'] = []
        for row in result:
            def format_date(date_value):
                if date_value is None:
                    return None
                if isinstance(date_value, str):
                    try:
                        # Se já é string, tenta converter para datetime primeiro
                        date_obj = datetime.strptime(date_value, '%Y-%m-%d %H:%M:%S')
                        return date_obj.isoformat()
                    except:
                        # Se não conseguir converter, retorna a string original
                        return date_value
                elif hasattr(date_value, 'isoformat'):
                    # Se é um objeto datetime, usa isoformat
                    return date_value.isoformat()
                elif hasattr(date_value, 'year'):
                    # Se é um objeto de data do Oracle, converte para datetime
                    date_obj = datetime(date_value.year, date_value.month, date_value.day, 
                                      getattr(date_value, 'hour', 0), 
                                      getattr(date_value, 'minute', 0), 
                                      getattr(date_value, 'second', 0))
                    return date_obj.isoformat()
                else:
                    return str(date_value)
            veiculo = {
                'cod_proposta': row[0] if row[0] != 0 else None,
                'data_proposta': format_date(row[1]),
                'cod_vendedor': row[2],
                'nome_vendedor': row[3],
                'modelo': row[4],
                'cor': row[5],
                'ano_modelo': row[6],
                'chassi_completo': row[7],
                'empresa': row[8],
                'emissao': format_date(row[9]),
                'patio': row[10],
                'cod_cliente': row[11],
                'nome_cliente': row[12],
                'novo_usado': row[13],
                'placa': row[14],
                'cidade': row[15],
                'andamento': None,
                'usado': None
            }
            query = f"""
            SELECT cav.DESCRICAO  FROM CAIUAS_ANDAMENTO_VEICULO cav
                WHERE chassi_completo = '{veiculo["chassi_completo"]}'
                AND created_at = (SELECT max(created_at) FROM CAIUAS_ANDAMENTO_VEICULO cav
                WHERE chassi_completo = '{veiculo["chassi_completo"]}')
                ORDER BY created_at DESC
            """
            cur_oracle.execute(query)
            andamento_result = cur_oracle.fetchone()
            if andamento_result:
                veiculo['andamento'] = andamento_result[0]
            
            query = f"""
                SELECT count(*) FROM VEIC_FORMAS_PAGAMENTO vfp
                LEFT JOIN FORMA_PGTO fp ON 1=1
                    AND fp.cod_empresa = vfp.COD_EMPRESA 
                    AND fp.COD_FORMA_PGTO = vfp.COD_FORMA_PGTO 
                WHERE 1=1
                    AND vfp.cod_proposta = '{veiculo["cod_proposta"]}'
                    AND lower(descricao) LIKE ('%usado%')
            """
            cur_oracle.execute(query)
            usado_result = cur_oracle.fetchone()
            if usado_result and usado_result[0] > 0:
                veiculo['usado'] = True
            retorno['veiculos'].append(veiculo)
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

@veiculos_bp.route('/api/veiculos/modelos', methods=['GET'])
@token_required
def veiculos_modelos():
    try:
        query = f"""
            SELECT pm.DESCRICAO_MODELO, pm.COD_PRODUTO, pm.COD_MODELO 
                    FROM PRODUTOS_MODELOS pm
                    WHERE 1=1
                        --AND pm.ATIVO = 'S'
                        and pm.internet = 'S'
                    order by pm.descricao_modelo
        """
        conn_oracle, cur_oracle = oracle()
        cur_oracle.execute(query)
        result = cur_oracle.fetchall()
        retorno = {}
        retorno['modelos'] = []
        for row in result:
            modelo = {
                'descricao_modelo': row[0],
                'cod_produto': row[1],
                'cod_modelo': row[2]
            }
            retorno['modelos'].append(modelo)
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
    
@veiculos_bp.route('/api/veiculos/produtos', methods=['GET'])
@token_required
def get_veiculos_produtos():
    try:
        search = request.args.get('search', None)
        # data = request.get_json()
        token_data = request.token_data
        email = token_data.get('email').strip().lower()
        current_page = int(request.args.get('current_page', 1))
        limit = int(request.args.get('limit', 10))
        
        query_search = ""
        if search:
            query_search = f" AND lower(pm.DESCRICAO_MODELO) LIKE ('%{search.lower()}%') "
            
        query = f"""
            SELECT 
                count(*)
            FROM produtos_modelos pm
            LEFT JOIN produtos p ON 1=1
                AND p.COD_PRODUTO = pm.COD_PRODUTO 
            WHERE 1=1
                {query_search}
                and p.descricao_produto IS NOT NULL
        """
        # return query
        conn_oracle, cur_oracle = oracle()
        
        cur_oracle.execute(query)
        total = cur_oracle.fetchone()[0]
        if total == 0:
            try:
                cur_oracle.close()
                conn_oracle.close()
            except:
                pass
            return jsonify({'status': 'error', 'message': 'Não há veículos com o filtro'}), 404
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
            return jsonify({'status': 'error', 'message': 'Página inválida'}), 400
        
        query = f"""
                SELECT *
                    FROM (
                        SELECT t.*, ROWNUM AS rn
                        FROM (
                            -- Sua query original com ORDER BY aqui dentro
                    SELECT
                    p.COD_PRODUTO,
                    trim(p.DESCRICAO_PRODUTO) AS DESCRICAO_PRODUTO,
                    pm.COD_MODELO ,
                    trim(pm.DESCRICAO_MODELO) AS DESCRICAO_MODELO,
                    (SELECT count(*) FROM reclamacoes_padroes_veic cz 
                        LEFT JOIN RECLAMACOES_PADROES rp ON 1=1
                            AND rp.COD_RECLAMACAO = cz.COD_RECLAMACAO 
                        WHERE cz.cod_produto = pm.cod_produto AND cz.cod_modelo =
                        pm.cod_modelo AND rp.ATIVO = 'S') qtd_kits
                    FROM produtos_modelos pm
                    LEFT JOIN produtos p ON 1=1
                    AND p.COD_PRODUTO = pm.COD_PRODUTO
                    WHERE 1=1
                        {query_search}
                        and p.descricao_produto IS NOT NULL
                    order by p.DESCRICAO_PRODUTO
                    ) t
                )
                WHERE
                    rn BETWEEN {start_row} AND {end_row}
            """
        # return query
        cur_oracle.execute(query)
        result = cur_oracle.fetchall()
        retorno = {}
        retorno['veiculos'] = []
        for row in result:
            veiculo = {
                'cod_produto': row[0],
                'descricao_produto': row[1],
                'cod_modelo': row[2],
                'descricao_modelo': row[3],
                'qtd_kits': row[4]
            }
            retorno['veiculos'].append(veiculo)
        retorno['total'] = total
        retorno['current_page'] = current_page
        retorno['total_pages'] = total_pages
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
    
@veiculos_bp.route('/api/veiculos/produtos/<int:cod_produto>', methods=['GET'])
@token_required
def show_veiculos_produtos(cod_produto):
    try:
        
        token_data = request.token_data
        
        conn_oracle, cur_oracle = oracle()
        query = f"""
                    SELECT
                    p.COD_PRODUTO,
                    trim(p.DESCRICAO_PRODUTO) AS DESCRICAO_PRODUTO,
                    pm.COD_MODELO ,
                    trim(pm.DESCRICAO_MODELO) AS DESCRICAO_MODELO,
                    (SELECT count(*) FROM reclamacoes_padroes_veic cz 
                        LEFT JOIN RECLAMACOES_PADROES rp ON 1=1
                            AND rp.COD_RECLAMACAO = cz.COD_RECLAMACAO 
                        WHERE cz.cod_produto = pm.cod_produto AND cz.cod_modelo =
                        pm.cod_modelo AND rp.ATIVO = 'S') qtd_kits
                    FROM produtos_modelos pm
                    LEFT JOIN produtos p ON 1=1
                    AND p.COD_PRODUTO = pm.COD_PRODUTO
                    WHERE 1=1
                        AND pm.cod_modelo = {cod_produto}
                        and p.descricao_produto IS NOT NULL
                """
        cur_oracle.execute(query)
        result = cur_oracle.fetchall()
        if len(result) == 0:
            try:
                cur_oracle.close()
                conn_oracle.close()
            except:
                pass
            return jsonify({'status': 'error', 'message': 'Não há veículos com o filtro'}), 404
        retorno = {}
        retorno['cod_produto'] = result[0][0]
        retorno['descricao_produto'] = result[0][1]
        retorno['cod_modelo'] = result[0][2]
        retorno['descricao_modelo'] = result[0][3]
        retorno['qtd_kits'] = result[0][4]
        retorno['kits'] = []
        query = f"""
            SELECT rp.COD_RECLAMACAO, trim(rp.RECLAMACAO) reclamacao, rp.OBSERVACAO
            FROM reclamacoes_padroes_veic cz
            LEFT JOIN RECLAMACOES_PADROES rp ON 1=1
                AND rp.COD_RECLAMACAO = cz.COD_RECLAMACAO 
            WHERE 1=1
                AND rp.ativo = 'S'
                AND cz.COD_MODELO = {result[0][2]}
                order by rp.RECLAMACAO
        """
        cur_oracle.execute(query)
        kits_result = cur_oracle.fetchall()
        for kit in kits_result:
            kit_info = {
                'cod_reclamacao': kit[0],
                'reclamacao': kit[1],
                'observacao': kit[2]
            }
            retorno['kits'].append(kit_info)
        
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
    
@veiculos_bp.route('/api/veiculos/produtos/remove_kit', methods=['POST'])
@token_required
def remove_kit_produto():
    try:
        data = request.get_json()
        token_data = request.token_data
        email = token_data.get('email').strip().lower()
        cod_acesso = 40203
        conn_oracle, cur_oracle = oracle()
        query = f"""
            SELECT saf2.COD_ACESSO 
                FROM empresas_usuarios eu
                LEFT JOIN SISTEMA_ACESSO_FUNCAO saf ON 1=1
                    AND saf.COD_FUNCAO = eu.COD_FUNCAO 
                LEFT JOIN SISTEMA_ACESSO_FUNCAO saf2 ON 1=1
                    AND saf2.COD_FUNCAO = eu.COD_FUNCAO 
                WHERE 1=1
                    AND eu.DEMITIDO <> 'S'
                    AND saf2.COD_ACESSO = '{cod_acesso}'
                    AND lower(eu.EMAIl) = '{email}'
                GROUP BY saf2.COD_ACESSO
        """
        cur_oracle.execute(query)
        rows = cur_oracle.fetchall()
        if len(rows) == 0:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': f'Usuário não autorizado - {cod_acesso}'}), 403
        cod_produto = data.get('cod_produto', None)
        cod_modelo = data.get('cod_modelo', None)
        cod_reclamacao = data.get('cod_reclamacao', None)
        if not cod_produto or not cod_modelo or not cod_reclamacao:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'cod_produto, cod_modelo e cod_reclamacao são obrigatórios'}), 400
        query = f"""
            SELECT count(*) FROM reclamacoes_padroes_veic cz
                WHERE cz.COD_PRODUTO = {cod_produto}
                AND cz.COD_MODELO = {cod_modelo}
                AND cz.COD_RECLAMACAO = {cod_reclamacao}
        """
        cur_oracle.execute(query)
        result = cur_oracle.fetchone()
        if result[0] == 0:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'Kit não encontrado para o produto/modelo'}), 404
        if result[0] > 1:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'Mais de um kit encontrado para o produto/modelo. Contate o suporte'}), 400
        query = f"""
            DELETE FROM reclamacoes_padroes_veic
                WHERE COD_PRODUTO = {cod_produto}
                AND COD_MODELO = {cod_modelo}
                AND COD_RECLAMACAO = {cod_reclamacao}
        """
        cur_oracle.execute(query)
        conn_oracle.commit()
        cur_oracle.close()
        conn_oracle.close()
        retorno = {}
        retorno['message'] = 'Kit removido com sucesso'
        return jsonify(retorno), 200
    except Exception as e:
        try:
            cur_oracle.close()
            conn_oracle.close()
        except:
            pass
        return jsonify({'status': 'error', 'message': str(e)}), 400

@veiculos_bp.route('/api/veiculos/produtos/adiciona_kit', methods=['POST'])
@token_required
def adiciona_kit_produto():
    try:
        data = request.get_json()
        token_data = request.token_data
        email = token_data.get('email').strip().lower()
        cod_acesso = 40203
        conn_oracle, cur_oracle = oracle()
        query = f"""
            SELECT saf2.COD_ACESSO 
                FROM empresas_usuarios eu
                LEFT JOIN SISTEMA_ACESSO_FUNCAO saf ON 1=1
                    AND saf.COD_FUNCAO = eu.COD_FUNCAO 
                LEFT JOIN SISTEMA_ACESSO_FUNCAO saf2 ON 1=1
                    AND saf2.COD_FUNCAO = eu.COD_FUNCAO 
                WHERE 1=1
                    AND eu.DEMITIDO <> 'S'
                    AND saf2.COD_ACESSO = '{cod_acesso}'
                    AND lower(eu.EMAIl) = '{email}'
                GROUP BY saf2.COD_ACESSO
        """
        cur_oracle.execute(query)
        rows = cur_oracle.fetchall()
        if len(rows) == 0:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': f'Usuário não autorizado - {cod_acesso}'}), 403
        cod_produto = data.get('cod_produto', None)
        cod_modelo = data.get('cod_modelo', None)
        cod_reclamacao = data.get('cod_reclamacao', None)
        if not cod_produto or not cod_modelo or not cod_reclamacao:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'cod_produto, cod_modelo e cod_reclamacao são obrigatórios'}), 400
        query = f"""
            SELECT count(*) FROM reclamacoes_padroes_veic cz
                WHERE cz.COD_PRODUTO = {cod_produto}
                AND cz.COD_MODELO = {cod_modelo}
                AND cz.COD_RECLAMACAO = {cod_reclamacao}
        """
        cur_oracle.execute(query)
        result = cur_oracle.fetchone()
        if result[0] > 0:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'Kit já cadastrado para o produto/modelo'}), 400
        query = f"""
            SELECT count(*) FROM RECLAMACOES_PADROES rp 
                WHERE 1=1
                AND rp.ATIVO = 'S'	
                AND rp.eh_kit = 'S'
                AND rp.COD_RECLAMACAO = {cod_reclamacao}
        """
        cur_oracle.execute(query)
        result = cur_oracle.fetchone()
        if result[0] == 0:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'Reclamação padrão não encontrada ou não é um kit'}), 404
        
        query = f"""
            insert into reclamacoes_padroes_veic (COD_PRODUTO, COD_MODELO, COD_RECLAMACAO)
                values ({cod_produto}, {cod_modelo}, {cod_reclamacao})
        """
        cur_oracle.execute(query)
        conn_oracle.commit()
        cur_oracle.close()
        conn_oracle.close()
        retorno = {}
        retorno['message'] = 'Kit adicionado com sucesso'
        return jsonify(retorno), 200
        
        
    except Exception as e:
        try:
            cur_oracle.close()
            conn_oracle.close()
        except:
            pass
        return jsonify({'status': 'error', 'message': str(e)}), 400
    
@veiculos_bp.route('/api/veiculos/reclamacoes_padroes', methods=['GET'])
@token_required
def list_reclamacoes_padroes():
    try:
        search = request.args.get('search', None)
        current_page = int(request.args.get('current_page', 1))
        search = request.args.get('search', None)
        limit = int(request.args.get('limit', 10))
        
        query_search = ""
        if search:
            query_search = f" AND lower(rp.RECLAMACAO) LIKE ('%{search.lower()}%') "
        query = f"""
            select count(*)
            from RECLAMACOES_PADROES rp
            LEFT JOIN reclamacoes_padroes_empresa rpe ON 1=1
                AND rpe.COD_RECLAMACAO = rp.COD_RECLAMACAO 
                AND rpe.cod_empresa = 11
            where 1=1
                {query_search}
                AND rp.eh_kit = 'S'
                AND rpe.ATIVO = 'S'
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
                    SELECT rp.COD_RECLAMACAO, trim(rp.reclamacao)
                    FROM reclamacoes_padroes rp
                    LEFT JOIN reclamacoes_padroes_empresa rpe ON 1=1
                        AND rpe.COD_RECLAMACAO = rp.COD_RECLAMACAO 
                        AND rpe.cod_empresa = 11
                    WHERE 1=1
                        {query_search}
                    AND rpe.ATIVO = 'S'	
                    AND rp.eh_kit = 'S'
                    ORDER BY rp.RECLAMACAO 
                    ) t
            )
            WHERE
                rn BETWEEN {start_row} AND {end_row}
        """
        cur_oracle.execute(query)
        result = cur_oracle.fetchall()
        retorno = {}
        retorno['reclamacoes_padroes'] = []
        retorno['total'] = total
        retorno['current_page'] = current_page
        retorno['total_pages'] = total_pages
        for row in result:
            reclamacao = {
                'cod_reclamacao': row[0],
                'reclamacao': row[1]
            }
            retorno['reclamacoes_padroes'].append(reclamacao)
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

