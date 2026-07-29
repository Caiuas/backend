from flask import Blueprint, jsonify, request
from database import oracle, chatwoot
from dotenv import load_dotenv
from datetime import datetime
from auth import token_required
import boto3
import jpype
load_dotenv()

veiculos_bp = Blueprint('veiculos', __name__)

def format_oracle_date(date_value):
    """Converte datas do Oracle para formato ISO"""
    if date_value is None:
        return None
    if isinstance(date_value, str):
        return date_value
    
    # Trata especificamente oracle.sql.TIMESTAMPTZ
    if hasattr(date_value, '__class__') and 'oracle.sql' in str(type(date_value)):
        try:
            # Converte para datetime do Python usando os atributos do objeto Oracle
            if hasattr(date_value, 'year'):
                date_obj = datetime(
                    date_value.year, 
                    date_value.month, 
                    date_value.day,
                    getattr(date_value, 'hour', 0),
                    getattr(date_value, 'minute', 0),
                    getattr(date_value, 'second', 0),
                    getattr(date_value, 'microsecond', 0)
                )
                return date_obj.isoformat()
        except Exception as e:
            return str(date_value)
    
    # Se é um objeto com atributos year, month, day
    if hasattr(date_value, 'year'):
        try:
            date_obj = datetime(
                date_value.year, 
                date_value.month, 
                date_value.day,
                getattr(date_value, 'hour', 0),
                getattr(date_value, 'minute', 0),
                getattr(date_value, 'second', 0),
                getattr(date_value, 'microsecond', 0)
            )
            return date_obj.isoformat()
        except Exception:
            return str(date_value)
    
    # Se já tem isoformat
    if hasattr(date_value, 'isoformat'):
        return date_value.isoformat()
    
    return str(date_value)

def _read_clob(clob_value):
    """Converte CLOB do Oracle para string Python"""
    if clob_value is None:
        return ''
    if hasattr(clob_value, 'read'):
        return clob_value.read()
    if hasattr(clob_value, 'getSubString'):
        length = int(clob_value.length())
        return str(clob_value.getSubString(jpype.JLong(1), length))
    return str(clob_value)

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
                END cidade,
                vp.DATA_VENDA
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
                'usado': None,
                'data_venda': format_date(row[16])
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
        --                and pm.internet = 'S'
                        and pm.cod_produto = '110589'
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

@veiculos_bp.route('/api/veiculos/processos', methods=['GET'])
@token_required
def list_processos():
    try:
        search = request.args.get('search', None)
        token_data = request.token_data
        email = token_data.get('email').strip().lower()
        current_page = int(request.args.get('current_page', 1))
        search = request.args.get('search', None)
        limit = int(request.args.get('limit', 10))
        retorno = {}
        cod_acesso = '50190'
        
        if search:
            search = f""" 
                AND (lower(c.NOME) LIKE ('%{search.lower()}%') 
                OR lower(cvp.responsible) LIKE ('%{search.lower()}%')) 
                or cvp.cod_proposta = '{search}'
                or lower(eu.nome_completo) LIKE ('%{search.lower()}%')
                """
        
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
        conn, cur = oracle()
        cur.execute(query)
        rows = cur.fetchall()
        filter_user = ''
        if len(rows) == 0:
            filter_user = f"""
                    AND lower(eu.EMAIl) = '{email}'
            """
        
        query = f"""
            SELECT 
                count(*)
            FROM caiuas_veic_proc cvp
                LEFT JOIN clientes c ON 1=1
                    AND c.cod_cliente = cvp.cod_cliente
                LEFT JOIN empresas_usuarios eu ON 1=1
		            AND eu.nome = cvp.responsible
            where 1=1
                    {filter_user}
        """
        cur.execute(query)
        total = cur.fetchone()[0]
        if total == 0:
            cur.close()
            conn.close()
            return jsonify({'status': 'error', 'message': 'Não há processos com o filtro'}), 204
        offset = (current_page - 1) * limit
        total_pages = (total + limit - 1) // limit
        start_row = (current_page - 1) * limit + 1
        end_row = current_page * limit
        
        query = f"""
            SELECT cvp.id_processo,
                cvp.responsible,
                TO_CHAR(cvp.created_at, 'YYYY-MM-DD"T"HH24:MI:SS') as created_at,
                TO_CHAR(cvp.updated_at, 'YYYY-MM-DD"T"HH24:MI:SS') as updated_at,
                cvp.tipo,
                cvp.status,
                c.cod_cliente, 
                c.NOME, 
                concat(c.PREFIXO_RES,c.TELEFONE_RES) tel_residencial,
                concat(c.PREFIXO_COM,c.TELEFONE_COM) tel_comercial,
                concat(c.PREFIXO_FAX,c.TELEFONE_FAX) tel_fax,
                concat(c.PREFIXO_MSG_TXT_INST,c.NUMERO_MSG_TXT_INST) tel_whatsapp,
                c.ENDERECO_ELETRONICO ,
                c.EMAIL2 ,
                c.EMAIL_NFE,
                eu.nome_completo nome_responsavel,
                cvp.cod_proposta
            FROM caiuas_veic_proc cvp
                LEFT JOIN clientes c ON 1=1
                    AND c.cod_cliente = cvp.cod_cliente
                LEFT JOIN empresas_usuarios eu ON 1=1
		AND eu.nome = cvp.responsible
            where 1=1
                {filter_user}
            order by cvp.updated_at desc
        """
        cur.execute(query)
        
        result = cur.fetchall()
        retorno['current_page'] = current_page
        retorno['total_pages'] = total_pages
        retorno['total'] = total
        retorno['processos'] = []
        for row in result:
            processo = {
                'id_processo': row[0],
                'created_at': row[2],
                'updated_at': row[3],
                'tipo': row[4],
                'status': row[5],
                'cod_proposta': row[16],
                'cliente': {
                    'cod_cliente': row[6],
                    'nome': row[7],
                    'tel_residencial': row[8],
                    'tel_comercial': row[9],
                    'tel_fax': row[10],
                    'tel_whatsapp': row[11],
                    'endereco_eletronico': row[12],
                    'email2': row[13],
                    'email_nfe': row[14]
                } if row[6] else {},
                'responsible': {
                    'nome_responsavel': row[15],
                    'cod_responsavel': row[1]
                } if row[15] else {}
            }
            
            if processo['tipo'] == 1:
                processo['tipo_descricao'] = 'Veículo novo'
            elif processo['tipo'] == 2:
                processo['tipo_descricao'] = 'Veículo usado'
            elif processo['tipo'] == 3:
                processo['tipo_descricao'] = 'PCD'
            else:
                processo['tipo_descricao'] = 'Desconhecido'
                   
            retorno['processos'].append(processo)
        cur.close()
        conn.close()
        
        
        
        return retorno, 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400
    
@veiculos_bp.route('/api/veiculos/processos', methods=['POST'])
@token_required
def create_processos():
    try:
        cod_cliente = request.json.get('cod_cliente', None)
        tipo = request.json.get('tipo', None)
        token_data = request.token_data
        if not cod_cliente or not tipo:
            return jsonify({'status': 'error', 'message': 'cod_cliente e tipo são obrigatórios'}), 400
        if tipo not in [1, 2, 3]:
            return jsonify({'status': 'error', 'message': 'tipo inválido. Valores permitidos: 1, 2, 3'}), 400
        email = token_data.get('email').strip().lower()
        conn, cur = oracle()
        query = f"""
            select count(*) from clientes c
            where 1=1
                and c.cod_cliente = '{cod_cliente}'
        """
        cur.execute(query)
        result = cur.fetchone()
        if result[0] == 0:
            cur.close()
            conn.close()
            return jsonify({'status': 'error', 'message': 'Cliente não encontrado'}), 400
        
        query = f"""
            select count(*) from empresas_usuarios eu
            where 1=1
                and lower(eu.email) = '{email}'
                and eu.cod_empresa in (11,33,111)
                AND eu.DEMITIDO = 'N'
        """
        cur.execute(query)
        result = cur.fetchone()
        if result[0] == 0:
            cur.close()
            conn.close()
            return jsonify({'status': 'error', 'message': 'Usuário não encontrado'}), 400
        
        query = f"""
            SELECT NVL(MAX(id_processo), 0) + 1 FROM caiuas_veic_proc
        """
        cur.execute(query)
        new_id = cur.fetchone()[0]
        
        query = f"""
            INSERT INTO caiuas_veic_proc (id_processo, cod_cliente, tipo, status, responsible, created_at, updated_at, ativo)
            SELECT 
                {new_id},
                '{cod_cliente}',
                {tipo},
                'Pendente',
                x.nome,
                SYSDATE,
                SYSDATE,
                1
            FROM (
                -- Subquery para buscar o usuário e ordenar
                SELECT eu.nome
                FROM empresas_usuarios eu
                WHERE lower(eu.email) = '{email}'
                and eu.cod_empresa in (11,33,111)
                AND eu.DEMITIDO = 'N'
                ORDER BY eu.cod_empresa ASC
            ) x
            WHERE ROWNUM = 1
        """
        cur.execute(query)
        conn.commit()
        query = f"""
            INSERT INTO CAIUAS_VEIC_PROC_ETAPAS (id_etapa, nome_etapa, autorizadores, tipo, id_processo, created_at, UPDATED_AT, explicacao, observacao)
            SELECT (SELECT NVL(MAX(id_etapa), 0) FROM CAIUAS_VEIC_PROC_ETAPAS) + ROWNUM AS id_etapa,
                nome_etapa, 
                autorizadores, 
                {tipo},
                {new_id},
                CURRENT_TIMESTAMP, 
                CURRENT_TIMESTAMP,
                explicacao,
                null
            FROM CAIUAS_VEIC_PROC_ET_MOD
            WHERE 1=1
                AND tipo = {tipo}
        """
        cur.execute(query)
        conn.commit()
        cur.close()
        conn.close()
        
        retorno = {}
        retorno['message'] = 'Processo criado com sucesso'
        
        return jsonify(retorno), 201
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@veiculos_bp.route('/api/veiculos/processos/obs_etapa', methods=['POST'])
@token_required
def add_obs_etapa():
    try:
        id_etapa = request.json.get('id_etapa', None)
        observacao = request.json.get('observacao', None)
        token_data = request.token_data
        email = token_data.get('email').strip().lower()
        if not id_etapa or not observacao:
            return jsonify({'status': 'error', 'message': 'id_etapa e observacao são obrigatórios'}), 400
        conn, cur = oracle()
        query = f"""
            select id_processo from CAIUAS_VEIC_PROC_ETAPAS
            where 1=1
                and id_etapa = {id_etapa}
        """
        cur.execute(query)
        id_processo = cur.fetchone()
        if not id_processo:
            cur.close()
            conn.close()
            return jsonify({'status': 'error', 'message': 'Etapa não encontrada'}), 400
        
        query = f"""
            UPDATE CAIUAS_VEIC_PROC_ETAPAS
            SET observacao = '{observacao}',
                updated_at = SYSDATE
            WHERE id_etapa = {id_etapa}
        """
        cur.execute(query)
        conn.commit()
        
        query = f"""
            SELECT 
                cvpe.id_etapa, 
                cvpe.nome_etapa, 
                cvpe.autorizadores, 
                cvpe.tipo, 
                cvpe.explicacao, 
                TO_CHAR(cvpe.created_at, 'YYYY-MM-DD"T"HH24:MI:SS') as created_at,
                TO_CHAR(cvpe.updated_at, 'YYYY-MM-DD"T"HH24:MI:SS') as updated_at,
                cvpe.observacao
            FROM CAIUAS_VEIC_PROC_ETAPAS cvpe 
            WHERE 1=1
                and cvpe.id_etapa = {id_etapa}
            ORDER BY cvpe.id_etapa
        """
        # return query
        cur.execute(query)
        etapas = cur.fetchall()
        retorno = {}
        for etapa in etapas:
            autorizadores = []
            aut = etapa[2].split(',') if etapa[2] else []
            for a in aut:
                query = f"""
                    SELECT eu.nome_completo, eu.EMAIL FROM EMPRESAS_USUARIOS eu
                    WHERE upper(nome) = '{a.strip().upper()}'
                """
                autorizador = {}
                cur.execute(query)
                result = cur.fetchone()
                if result:
                    autorizador['nome_completo'] = result[0]
                    autorizador['usuario_nbs'] = str(a).upper().strip()
                    autorizador['email'] = result[1]
                    query = f"""
                        SELECT 
                            TO_CHAR(cvpea.created_at, 'YYYY-MM-DD"T"HH24:MI:SS') as created_at,
                            TO_CHAR(cvpea.updated_at, 'YYYY-MM-DD"T"HH24:MI:SS') as updated_at
                        FROM CAIUAS_VEIC_PROC_ETAPAS_AUT cvpea
                        WHERE 1=1
                            AND cvpea.autorizador = '{a.strip().upper()}'
                            AND cvpea.id_etapa = {etapa[0]}
                    """
                    cur.execute(query)
                    aut_info = cur.fetchone()
                    if aut_info:
                        autorizador['created_at'] = aut_info[0]
                        autorizador['updated_at'] = aut_info[1]
                        autorizador['status'] = 'Autorizado'
                    else:
                        autorizador['created_at'] = None
                        autorizador['updated_at'] = None
                        autorizador['status'] = 'Pendente'
                    autorizadores.append(autorizador)
            etapa_info = {
                'id_etapa': etapa[0],
                'nome_etapa': etapa[1],
                'autorizadores': autorizadores,
                'tipo': etapa[3],
                # essa explicação é um clob, converta para o texto
                'explicacao': _read_clob(etapa[4]),
                'observacao': _read_clob(etapa[7]),
                'created_at': etapa[5],
                'updated_at': etapa[6],
                'arquivos': []
            }
            retorno['etapa'] = etapa_info
        query = f"""
            update caiuas_veic_proc
            set updated_at = SYSDATE
            where id_processo = {id_processo[0]}
        """
        cur.execute(query)
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify(retorno), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400
    
@veiculos_bp.route('/api/veiculos/processos/desativa', methods=['POST'])
@token_required
def desativa_processo():
    try:
        id_processo = request.json.get('id_processo', None)
        token_data = request.token_data
        cod_acesso = '50190'
        if not id_processo:
            return jsonify({'status': 'error', 'message': 'id_processo é obrigatório'}), 400
        email = token_data.get('email').strip().lower()
        
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
        conn, cur = oracle()
        cur.execute(query)
        rows = cur.fetchall()
        filter_user = ''
        if len(rows) == 0:
            filter_user = f"""
                AND c.cod_cliente IN (
                SELECT nome FROM empresas_usuarios eu
                WHERE 1=1
                    AND lower(eu.EMAIl) = '{email}'
                )
            """
        
        query = f"""
            select count(*) from caiuas_veic_proc cvp
            where 1=1
                and cvp.id_processo = {id_processo}
                and cvp.ativo = 1
                {filter_user}
        """
        cur.execute(query)
        result = cur.fetchone()
        if result[0] == 0:
            cur.close()
            conn.close()
            return jsonify({'status': 'error', 'message': 'Processo não encontrado'}), 400
        
        query = f"""
            UPDATE caiuas_veic_proc
            SET ativo = 0,
                status = 'Excluido',
                updated_at = SYSDATE
            WHERE id_processo = {id_processo}
        """
        cur.execute(query)
        conn.commit()
        cur.close()
        conn.close()
        retorno = {}
        retorno['message'] = 'Processo desativado com sucesso'
        
        return jsonify(retorno), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400
    
@veiculos_bp.route('/api/veiculos/processos/<int:id_processo>', methods=['GET'])
@token_required
def show_processo(id_processo):
    try:
        token_data = request.token_data
        email = token_data.get('email').strip().lower()
        cod_acesso = '50190'
        
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
        conn, cur = oracle()
        cur.execute(query)
        rows = cur.fetchall()
        filter_user = ''
        if len(rows) == 0:
            filter_user = f"""
                    AND lower(eu.EMAIl) = '{email}'
            """
            
        query = f"""
            SELECT cvp.id_processo,
                cvp.responsible,
                TO_CHAR(cvp.created_at, 'YYYY-MM-DD"T"HH24:MI:SS') as created_at,
                TO_CHAR(cvp.updated_at, 'YYYY-MM-DD"T"HH24:MI:SS') as updated_at,
                cvp.tipo,
                cvp.status,
                c.cod_cliente, 
                c.NOME, 
                concat(c.PREFIXO_RES,c.TELEFONE_RES) tel_residencial,
                concat(c.PREFIXO_COM,c.TELEFONE_COM) tel_comercial,
                concat(c.PREFIXO_FAX,c.TELEFONE_FAX) tel_fax,
                concat(c.PREFIXO_MSG_TXT_INST,c.NUMERO_MSG_TXT_INST) tel_whatsapp,
                c.ENDERECO_ELETRONICO ,
                c.EMAIL2 ,
                c.EMAIL_NFE,
                eu.nome_completo nome_responsavel,
                cvp.cod_proposta
            FROM caiuas_veic_proc cvp
                LEFT JOIN clientes c ON 1=1
                    AND c.cod_cliente = cvp.cod_cliente
                LEFT JOIN empresas_usuarios eu ON 1=1
		            AND eu.nome = cvp.responsible
            where 1=1
                and cvp.id_processo = {id_processo}
                {filter_user}
            order by cvp.updated_at desc
        """
        cur.execute(query)
        rows = cur.fetchall()
        if len(rows) == 0:
            cur.close()
            conn.close()
            return jsonify({'status': 'error', 'message': 'Processo não encontrado'}), 404
        retorno = {}
        for row in rows:
            processo = {
                'id_processo': row[0],
                'created_at': row[2],
                'updated_at': row[3],
                'tipo': row[4],
                'status': row[5],
                'cod_proposta': row[16],
                'cliente': {
                    'cod_cliente': row[6],
                    'nome': row[7],
                    'tel_residencial': row[8],
                    'tel_comercial': row[9],
                    'tel_fax': row[10],
                    'tel_whatsapp': row[11],
                    'endereco_eletronico': row[12],
                    'email2': row[13],
                    'email_nfe': row[14]
                } if row[6] else {},
                'responsible': {
                    'nome_responsavel': row[15],
                    'cod_responsavel': row[1]
                } if row[15] else {}
            }
            
            if processo['tipo'] == 1:
                processo['tipo_descricao'] = 'Veículo novo'
            elif processo['tipo'] == 2:
                processo['tipo_descricao'] = 'Veículo usado'
            elif processo['tipo'] == 3:
                processo['tipo_descricao'] = 'PCD'
            else:
                processo['tipo_descricao'] = 'Desconhecido'
                   
            retorno = processo
        query = f"""
            SELECT 
                cvpe.id_etapa, 
                cvpe.nome_etapa, 
                cvpe.autorizadores, 
                cvpe.tipo, 
                cvpe.explicacao, 
                TO_CHAR(cvpe.created_at, 'YYYY-MM-DD"T"HH24:MI:SS') as created_at,
                TO_CHAR(cvpe.updated_at, 'YYYY-MM-DD"T"HH24:MI:SS') as updated_at,
                cvpe.observacao,
                cvpe.status
            FROM CAIUAS_VEIC_PROC_ETAPAS cvpe 
            WHERE 1=1
                and cvpe.tipo = {retorno['tipo']}
                and cvpe.id_processo = {id_processo}
            ORDER BY cvpe.id_etapa
        """
        # return query
        cur.execute(query)
        etapas = cur.fetchall()
        retorno['etapas'] = []
        for etapa in etapas:
            autorizadores = []
            aut = etapa[2].split(',') if etapa[2] else []
            for a in aut:
                query = f"""
                    SELECT eu.nome_completo, eu.EMAIL FROM EMPRESAS_USUARIOS eu
                    WHERE upper(nome) = '{a.strip().upper()}'
                """
                autorizador = {}
                cur.execute(query)
                result = cur.fetchone()
                if result:
                    autorizador['nome_completo'] = result[0]
                    autorizador['usuario_nbs'] = str(a).upper().strip()
                    autorizador['email'] = result[1]
                    query = f"""
                        SELECT 
                            TO_CHAR(cvpea.created_at, 'YYYY-MM-DD"T"HH24:MI:SS') as created_at,
                            TO_CHAR(cvpea.updated_at, 'YYYY-MM-DD"T"HH24:MI:SS') as updated_at
                        FROM CAIUAS_VEIC_PROC_ETAPAS_AUT cvpea
                        WHERE 1=1
                            AND cvpea.autorizador = '{a.strip().upper()}'
                            AND cvpea.id_etapa = {etapa[0]}
                    """
                    cur.execute(query)
                    aut_info = cur.fetchone()
                    if aut_info:
                        autorizador['created_at'] = aut_info[0]
                        autorizador['updated_at'] = aut_info[1]
                        autorizador['status'] = 'Autorizado'
                    else:
                        autorizador['created_at'] = None
                        autorizador['updated_at'] = None
                        autorizador['status'] = 'Pendente'
                    autorizadores.append(autorizador)
            etapa_info = {
                'id_etapa': etapa[0],
                'nome_etapa': etapa[1],
                'autorizadores': autorizadores,
                'tipo': etapa[3],
                # essa explicação é um clob, converta para o texto
                'explicacao': _read_clob(etapa[4]),
                'observacao': _read_clob(etapa[7]),
                'created_at': etapa[5],
                'updated_at': etapa[6],
                'status': etapa[8],
                'arquivos': []
            }
            query = f"""
            SELECT cvpef.id_file_etapa, cvpef.id_etapa, cvpef.id_file,
            cf.id_file, cf.file_key, cf.bucket, cf.file_size, cf.content_type, cf.region, cf.created_at, cf.old_file_name
            FROM CAIUAS_VEIC_PROC_ETAPAS_files cvpef
            LEFT JOIN caiuas_files cf ON 1=1
                AND cf.id_file = cvpef.id_file
            WHERE 1=1
                and cvpef.id_etapa = {etapa[0]}
            """
            cur.execute(query)
            arquivos = cur.fetchall()
            for arquivo in arquivos:
                arquivo_info = {
                    'id_file_etapa': arquivo[0],
                    'id_etapa': arquivo[1],
                    'id_file': arquivo[2],
                    'file_key': arquivo[4],
                    'bucket': arquivo[5],
                    'file_size': arquivo[6],
                    'content_type': arquivo[7],
                    'region': arquivo[8],
                    'created_at': arquivo[9],
                    'old_file_name': arquivo[10]
                }
                etapa_info['arquivos'].append(arquivo_info)
            
            retorno['etapas'].append(etapa_info)
        
        query = f"""
            select 
            cvpef.id_file_proc, cvpef.id_file,
            cf.id_file, cf.file_key, cf.bucket, cf.file_size, cf.content_type, cf.region, cf.created_at, cf.old_file_name
            from CAIUAS_VEIC_PROC_FILES cvpef
            LEFT JOIN caiuas_files cf ON 1=1
                AND cf.id_file = cvpef.id_file
            where 1=1
                and cvpef.id_processo = {id_processo}
        """
        cur.execute(query)
        arquivos = cur.fetchall()
        retorno['arquivos'] = []
        for arquivo in arquivos:
            arquivo_info = {
                'id_file_proc': arquivo[0],
                'id_file': arquivo[1],
                'file_key': arquivo[3],
                'bucket': arquivo[4],
                'file_size': arquivo[5],
                'content_type': arquivo[6],
                'region': arquivo[7],
                'created_at': arquivo[8],
                'old_file_name': arquivo[9]
            }
            retorno['arquivos'].append(arquivo_info)
        
        cur.close()
        conn.close()
        
        return jsonify(retorno), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400
    
@veiculos_bp.route('/api/veiculos/processos/<int:id_processo>/proposta', methods=['PUT'])
@token_required
def add_proposta(id_processo):
    try:
        cod_proposta = request.json.get('cod_proposta', None)
        token_data = request.token_data
        email = token_data.get('email').strip().lower()
        if not cod_proposta:
            return jsonify({'status': 'error', 'message': 'cod_proposta é obrigatório'}), 400
        conn, cur = oracle()
        query = f"""
            select count(*) from caiuas_veic_proc
            where 1=1
                and id_processo = {id_processo}
        """
        cur.execute(query)
        result = cur.fetchone()
        if result[0] == 0:
            cur.close()
            conn.close()
            return jsonify({'status': 'error', 'message': 'Processo não encontrado'}), 400
        
        # Verifica se a proposta já está vinculada a outro processo
        query = f"""
            SELECT id_processo FROM caiuas_veic_proc
            WHERE 1=1
                AND cod_proposta = '{cod_proposta}'
                AND id_processo <> {id_processo}
        """
        cur.execute(query)
        proposta_existente = cur.fetchone()
        if proposta_existente:
            cur.close()
            conn.close()
            return jsonify({'status': 'error', 'message': f'Proposta já vinculada ao processo {proposta_existente[0]}'}), 400
        
        query = f"""
            UPDATE caiuas_veic_proc
            SET cod_proposta = '{cod_proposta}',
                updated_at = SYSDATE
            WHERE id_processo = {id_processo}
        """
        cur.execute(query)
        conn.commit()
        
        cur.close()
        conn.close()
        
        retorno = {}
        retorno['message'] = 'Proposta adicionada com sucesso'
        
        return jsonify(retorno), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@veiculos_bp.route('/api/veiculos/processos/<int:id_processo>/reabre', methods=['PUT'])
@token_required
def reabre_processo(id_processo):
    try:
        token_data = request.token_data
        email = token_data.get('email').strip().lower()
        permissao = '50190'
        conn, cur = oracle()
        query = f"""
            select count(*) from caiuas_veic_proc
            where 1=1
                and id_processo = {id_processo}
        """
        
        cur.execute(query)
        result = cur.fetchone()
        
        # se naõ tiver permissão naõ pode reabrir
        query = f"""
            SELECT saf2.COD_ACESSO 
                FROM empresas_usuarios eu
                LEFT JOIN SISTEMA_ACESSO_FUNCAO saf ON 1=1
                    AND saf.COD_FUNCAO = eu.COD_FUNCAO
                LEFT JOIN SISTEMA_ACESSO_FUNCAO saf2 ON 1=1
                    AND saf2.COD_FUNCAO = eu.COD_FUNCAO
                WHERE 1=1
                    AND eu.DEMITIDO <> 'S'
                    AND saf2.COD_ACESSO = '{permissao}'
                    AND lower(eu.EMAIl) = '{email}'
                GROUP BY saf2.COD_ACESSO
        """
        cur.execute(query)
        rows = cur.fetchall()
        if len(rows) == 0:
            cur.close()
            conn.close()
            return jsonify({'status': 'error', 'message': 'Usuário não tem permissão para reabrir processos'}), 403
        
        
        if result[0] == 0:
            cur.close()
            conn.close()
            return jsonify({'status': 'error', 'message': 'Processo não encontrado ou não está excluído'}), 400
        
        query = f"""
            UPDATE caiuas_veic_proc
            SET ativo = 1,
                status = 'Pendente',
                updated_at = SYSDATE
            WHERE id_processo = {id_processo}
        """
        cur.execute(query)
        conn.commit()
        
        cur.close()
        conn.close()
        
        retorno = {}
        retorno['message'] = 'Processo reaberto com sucesso'
        
        return jsonify(retorno), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@veiculos_bp.route('/api/veiculos/processos/<int:id_processo>/finalizar', methods=['PUT'])
@token_required
def finaliza_processo(id_processo):
    try:
        token_data = request.token_data
        email = token_data.get('email').strip().lower()
        
        conn, cur = oracle()
        
        # Verifica se o processo existe
        query = f"""
            SELECT status FROM caiuas_veic_proc
            WHERE 1=1
                AND id_processo = {id_processo}
                AND ativo = 1
        """
        cur.execute(query)
        result = cur.fetchone()
        
        if not result:
            cur.close()
            conn.close()
            return jsonify({'status': 'error', 'message': 'Processo não encontrado'}), 404
        
        status_atual = result[0]
        
        if status_atual == 'Finalizado':
            cur.close()
            conn.close()
            return jsonify({'status': 'error', 'message': 'Processo já está finalizado'}), 400
        
        # Verifica se todas as etapas estão concluídas
        query = f"""
            SELECT COUNT(*)
            FROM CAIUAS_VEIC_PROC_ETAPAS
            WHERE id_processo = {id_processo}
              AND (status IS NULL OR status <> 'Autorizado')
        """
        cur.execute(query)
        etapas_pendentes = cur.fetchone()[0]
        
        if etapas_pendentes > 0:
            cur.close()
            conn.close()
            return jsonify({'status': 'error', 'message': f'Não é possível finalizar. Existem {etapas_pendentes} etapa(s) não concluída(s)'}), 400
        
        # Finaliza o processo
        query = f"""
            UPDATE caiuas_veic_proc
            SET status = 'Autorizado',
                updated_at = SYSDATE
            WHERE id_processo = {id_processo}
        """
        cur.execute(query)
        conn.commit()
        
        cur.close()
        conn.close()
        
        retorno = {}
        retorno['message'] = 'Processo finalizado com sucesso'
        
        return jsonify(retorno), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400


@veiculos_bp.route('/api/veiculos/processos/autorizar', methods=['POST'])
@token_required
def autorizar_etapa():
    try:
        id_etapa = request.json.get('id_etapa', None)
        usuario_nbs = request.json.get('usuario_nbs', None)  # Autorizador específico enviado pelo frontend
        token_data = request.token_data
        email = token_data.get('email').strip().lower()
        
        if not id_etapa:
            return jsonify({'status': 'error', 'message': 'id_etapa é obrigatório'}), 400
        
        if not usuario_nbs:
            return jsonify({'status': 'error', 'message': 'usuario_nbs é obrigatório'}), 400
        
        usuario_nbs = usuario_nbs.strip().upper()
        
        conn, cur = oracle()
        
        # 1. Busca o nome do usuário pelo email
        query = f"""
            SELECT eu.NOME
            FROM empresas_usuarios eu
            WHERE lower(eu.EMAIL) = '{email}'
        """
        cur.execute(query)
        results = cur.fetchall()
        
        if not results:
            cur.close()
            conn.close()
            return jsonify({'status': 'error', 'message': 'Usuário não encontrado'}), 400
        
        # Lista de nomes do usuário (pode ter mais de um)
        nomes_usuario = [str(row[0]).upper().strip() for row in results]
        
        # 2. Verifica se o usuario_nbs enviado pertence ao usuário logado
        if usuario_nbs not in nomes_usuario:
            cur.close()
            conn.close()
            return jsonify({'status': 'error', 'message': 'Não pode autorizar etapa por outro usuário'}), 403
        
        # 3. Busca os autorizadores da etapa
        query = f"""
            SELECT cvpe.AUTORIZADORES, cvpe.ID_PROCESSO
            FROM CAIUAS_VEIC_PROC_ETAPAS cvpe
            WHERE cvpe.ID_ETAPA = {id_etapa}
        """
        cur.execute(query)
        result = cur.fetchone()
        
        if not result:
            cur.close()
            conn.close()
            return jsonify({'status': 'error', 'message': 'Etapa não encontrada'}), 404
        
        autorizadores = result[0]
        id_processo = result[1]
        
        if not autorizadores:
            cur.close()
            conn.close()
            return jsonify({'status': 'error', 'message': 'Etapa não possui autorizadores configurados'}), 400
        
        # 4. Verifica se o usuario_nbs está na lista de autorizadores da etapa
        autorizadores_list = [a.strip().upper() for a in autorizadores.split(',')]
        
        if usuario_nbs not in autorizadores_list:
            cur.close()
            conn.close()
            return jsonify({'status': 'error', 'message': 'Usuário não é autorizador desta etapa'}), 400
        
        # 5. Verifica se já existe autorização para este usuario_nbs específico
        query = f"""
            SELECT AUTORIZADOR, id_autorizacao
            FROM CAIUAS_VEIC_PROC_ETAPAS_AUT
            WHERE ID_ETAPA = {id_etapa}
              AND UPPER(AUTORIZADOR) = '{usuario_nbs}'
        """
        cur.execute(query)
        autorizacao_existente = cur.fetchone()
        
        if autorizacao_existente:
            # Já existe autorização para este usuario_nbs
            # Verifica se deve remover (precisa do parâmetro remove_status)
            remove_status = request.json.get('remove_status', False)
            
            if not remove_status:
                cur.close()
                conn.close()
                return jsonify({
                    'status': 'info',
                    'message': 'Autorização já existe',
                    'autorizador': usuario_nbs,
                    'id_etapa': id_etapa,
                    'acao': 'ja_autorizado'
                }), 200
            
            # remove_status = True → remover autorização
            id_autorizacao = autorizacao_existente[1]
            
            # Verifica se o processo já está com status Autorizado
            query = f"""
                SELECT STATUS
                FROM caiuas_veic_proc
                WHERE id_processo = {id_processo}
            """
            cur.execute(query)
            status_processo = cur.fetchone()
            
            if status_processo and status_processo[0] == 'Autorizado':
                cur.close()
                conn.close()
                return jsonify({'status': 'error', 'message': 'Não é possível remover autorização de um processo já autorizado'}), 400
            
            # Remove a autorização existente pelo ID específico
            query = f"""
                DELETE FROM CAIUAS_VEIC_PROC_ETAPAS_AUT
                WHERE ID_AUTORIZACAO = {id_autorizacao}
            """
            cur.execute(query)
            
            # Atualiza o status da etapa para Pendente
            query = f"""
                UPDATE CAIUAS_VEIC_PROC_ETAPAS
                SET STATUS = 'Pendente',
                    UPDATED_AT = SYSDATE
                WHERE ID_ETAPA = {id_etapa}
            """
            cur.execute(query)
            
            # Atualiza o updated_at do processo
            query = f"""
                UPDATE caiuas_veic_proc
                SET updated_at = SYSDATE
                WHERE id_processo = {id_processo}
            """
            cur.execute(query)
            conn.commit()
            
            cur.close()
            conn.close()
            
            return jsonify({
                'status': 'success',
                'message': 'Autorização removida com sucesso',
                'autorizador': usuario_nbs,
                'id_etapa': id_etapa,
                'acao': 'removido'
            }), 200
        
        # 6. Não existe autorização → adicionar para o usuario_nbs
        query = f"""
            INSERT INTO CAIUAS_VEIC_PROC_ETAPAS_AUT (ID_AUTORIZACAO, ID_ETAPA, AUTORIZADOR, CREATED_AT, UPDATED_AT)
            VALUES (
                (SELECT NVL(MAX(ID_AUTORIZACAO), 0) + 1 FROM CAIUAS_VEIC_PROC_ETAPAS_AUT),
                {id_etapa},
                '{usuario_nbs}',
                SYSDATE,
                SYSDATE
            )
        """
        cur.execute(query)
        
        # 7. Verifica se todas as autorizações da etapa foram preenchidas
        total_autorizadores = len(autorizadores_list)
        
        query = f"""
            SELECT COUNT(*)
            FROM CAIUAS_VEIC_PROC_ETAPAS_AUT
            WHERE ID_ETAPA = {id_etapa}
        """
        cur.execute(query)
        total_autorizacoes = cur.fetchone()[0]
        
        etapa_autorizada = False
        processo_autorizado = False
        
        if total_autorizacoes >= total_autorizadores:
            # Todas as autorizações preenchidas → marca etapa como Autorizado
            query = f"""
                UPDATE CAIUAS_VEIC_PROC_ETAPAS
                SET STATUS = 'Autorizado',
                    UPDATED_AT = SYSDATE
                WHERE ID_ETAPA = {id_etapa}
            """
            cur.execute(query)
            etapa_autorizada = True
            
            # 8. Verifica se todas as etapas do processo estão autorizadas
            query = f"""
                SELECT COUNT(*)
                FROM CAIUAS_VEIC_PROC_ETAPAS
                WHERE ID_PROCESSO = {id_processo}
                  AND (STATUS IS NULL OR STATUS <> 'Autorizado')
            """
            cur.execute(query)
            etapas_pendentes = cur.fetchone()[0]
            
            if etapas_pendentes == 0:
                # Todas as etapas autorizadas → marca processo como Autorizado
                query = f"""
                    UPDATE CAIUAS_VEIC_PROC
                    SET STATUS = 'Autorizado',
                        UPDATED_AT = SYSDATE
                    WHERE ID_PROCESSO = {id_processo}
                """
                cur.execute(query)
                processo_autorizado = True
        
        # 9. Atualiza o updated_at do processo
        query = f"""
            UPDATE caiuas_veic_proc
            SET updated_at = SYSDATE
            WHERE id_processo = {id_processo}
        """
        cur.execute(query)
        conn.commit()
        
        cur.close()
        conn.close()
        
        response_data = {
            'status': 'success',
            'message': 'Etapa autorizada com sucesso',
            'autorizador': usuario_nbs,
            'id_etapa': id_etapa,
            'acao': 'autorizado',
            'etapa_autorizada': etapa_autorizada,
            'processo_autorizado': processo_autorizado
        }
        
        return jsonify(response_data), 200
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400
    
@veiculos_bp.route('/api/veiculos/propostas', methods=['GET'])
@token_required
def list_propostas():
    try:
        token_data = request.token_data
        email = token_data.get('email').strip().lower()
        cod_proposta = request.args.get('cod_proposta', None)
        cod_cliente = request.args.get('cod_cliente', None)
        search = request.args.get('search', None)
        cod_acesso = '50190'
        current_page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 10))
        
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
        conn, cur = oracle()
        cur.execute(query)
        rows = cur.fetchall()
        filter_user = ''
        if len(rows) == 0:
            filter_user = f"""
                    AND lower(eu.EMAIl) = '{email}'
            """
        filter_cod_proposta = ''
        if cod_proposta:
            filter_cod_proposta = f"""
                AND vp.COD_PROPOSTA = '{cod_proposta}'
            """
        filter_cod_cliente = ''
        if cod_cliente:
            filter_cod_cliente = f"""
                AND vp.COD_CLIENTE = '{cod_cliente}'
            """    
        filter_search = ''
        if search:
            filter_search = f"""
                AND (
                    vp.COD_PROPOSTA LIKE '%{search}%'
                    OR c.NOME LIKE '%{search}%'
                    OR pm.DESCRICAO_MODELO LIKE '%{search}%'
                )
            """
        query = f"""
        SELECT vp.COD_PROPOSTA, vp.EMISSAO,c.COD_CLIENTE, c.NOME nome_cliente, pm.DESCRICAO_MODELO, vp.VALOR_PROPOSTA,cvp.ID_PROCESSO
            FROM veiculos_propostas vp
            LEFT JOIN EMPRESAS_USUARIOS eu ON 1=1
                AND eu.NOME = vp.VENDEDOR
            LEFT JOIN PRODUTOS_MODELOS pm ON 1=1
                AND pm.COD_PRODUTO = vp.COD_PRODUTO 
                AND pm.COD_MODELO = vp.COD_MODELO 
            LEFT JOIN clientes c ON 1=1
                AND c.COD_CLIENTE = vp.COD_CLIENTE 
            LEFT JOIN caiuas_veic_proc cvp ON 1=1
	            AND cvp.COD_PROPOSTA = vp.COD_PROPOSTA 
            WHERE 1=1
                AND vp.STATUS_PROPOSTA in ('A','V')
                {filter_user}
                {filter_cod_proposta}
                {filter_cod_cliente}
                {filter_search}
            ORDER BY vp.EMISSAO
        """
        
        cur.execute(query)
        result = cur.fetchall()
        
        total = len(result)
        if total == 0:
            cur.close()
            conn.close()
            return jsonify({'status': 'success', 'propostas': []}), 204
        retorno = {}
        retorno['propostas'] = []
        for row in result:
            proposta = {
                'cod_proposta': row[0],
                'emissao': row[1],
                'cod_cliente': row[2],
                'nome_cliente': row[3],
                'descricao_modelo': row[4],
                'valor_proposta': float(row[5]) if row[5] else None,
                'id_processo': row[6]
            }
            retorno['propostas'].append(proposta)
        retorno['total'] = total
        retorno['page'] = current_page
        retorno['limit'] = limit
        cur.close()
        conn.close()
        return jsonify(retorno), 200
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400
    
@veiculos_bp.route('/api/veiculos/propostas/<cod_proposta>', methods=['GET'])
@token_required
def get_proposta_details(cod_proposta):
    try:
        cod_proposta = int(cod_proposta)
        if not cod_proposta:
            return jsonify({'status': 'error', 'message': 'Código da proposta inválido'}), 400
        
        query = f"""
            SELECT
                vp.COD_PROPOSTA,
                vp.STATUS_PROPOSTA,
                vp.EMISSAO,
                pm.DESCRICAO_MODELO,
                v.CHASSI_COMPLETO,
                v.NOVO_USADO,
                v.COR_EXTERNA,
                CASE 
                    WHEN ce.descricao IS NOT NULL THEN ce.descricao
                    ELSE ce2.DESCRICAO
                END cor_externa,
                vp.INTERNET,
                c.NOME,
                c.COD_CLIENTE cpf_cnpj,
                c.email_nfe,
                concat(c.PREFIXO_RES, c.TELEFONE_RES) AS tel_residencial,
                concat(c.PREFIXO_COM, c.TELEFONE_COM) AS tel_comercial,
                concat(c.PREFIXO_FAX, c.TELEFONE_FAX) AS tel_fax,
                concat(c.PREFIXO_MSG_TXT_INST, c.NUMERO_MSG_TXT_INST) AS tel_whatsapp,
                vp.PRECO_BASICO ,
                vp.DESCONTO ,
                vp.VALOR_PROPOSTA ,
                vp.DESCONTO_INCONDICIONAL ,
                vpo.OBSERVACAO,
                eu.NOME_COMPLETO vendedor 
            FROM veiculos_propostas vp
            LEFT JOIN clientes c ON 1=1
                AND c.COD_CLIENTE = vp.cod_cliente
            LEFT JOIN PRODUTOS_MODELOS pm ON 1=1
                AND pm.COD_PRODUTO = vp.COD_PRODUTO 
                AND pm.cod_modelo = vp.COD_MODELO
            LEFT JOIN veiculos v ON 1=1
                AND v.CHASSI_RESUMIDO = vp.CHASSI_RESUMIDO
            LEFT JOIN prop_ficticia_dados pfd ON 1=1
                AND pfd.COD_FICTICIO = vp.COD_FICTICIO
            LEFT JOIN CORES_EXTERNAS ce ON 1=1
                AND ce.COR_EXTERNA = v.COR_EXTERNA
            LEFT JOIN CORES_EXTERNAS ce2 ON 1=1
                AND ce2.COR_EXTERNA = pfd.COR_EXTERNA 
            LEFT JOIN VEICULOS_PROPOSTAS_OBS vpo ON 1=1
                AND vpo.COD_PROPOSTA = vp.COD_PROPOSTA 
            LEFT JOIN EMPRESAS_USUARIOS eu ON 1=1
	            AND eu.NOME = vp.VENDEDOR 
            WHERE 1=1
                AND vp.COD_PROPOSTA = '{cod_proposta}'
                AND vp.STATUS_PROPOSTA IS not null
        """
        
        conn, cur = oracle()
        cur.execute(query)
        r = cur.fetchall()
        if len(r) == 0:
            cur.close()
            conn.close()
            return jsonify({'status': 'error', 'message': 'Proposta não encontrada'}), 404
        proposta = {
            'cod_proposta': r[0][0],
            'status_proposta': r[0][1],
            'emissao': r[0][2],
            'descricao_modelo': r[0][3],
            'chassi_completo': r[0][4],
            'novo_usado': r[0][5],
            'cor_externa': r[0][6],
            'cor_externa_descricao': r[0][7],
            'internet': r[0][8],
            'nome': r[0][9],
            'cpf_cnpj': r[0][10],
            'email_nfe': r[0][11],
            'tel_residencial': r[0][12],
            'tel_comercial': r[0][13],
            'tel_fax': r[0][14],
            'tel_whatsapp': r[0][15],
            'preco_basico': float(r[0][16]) if r[0][16] else None,
            'desconto': float(r[0][17]) if r[0][17] else None,
            'valor_proposta': float(r[0][18]) if r[0][18] else None,
            'desconto_incondicional': float(r[0][19]) if r[0][19] else None,
            'observacao': r[0][20],
            'vendedor': r[0][21]
        }
        # se internet = F e novo_usado = N tipo_proposta = Frotista
        # se internet = N e novo_usado = N tipo_proposta = Novo
        # se internet = N e novo_usado = U tipo_proposta = Usado
        # se internet = F e novo_usado = U tipo_proposta = Indefinido
        if proposta['internet'] == 'F' and proposta['novo_usado'] == 'N':
            proposta['tipo_proposta'] = 'Frotista'
        elif proposta['internet'] == 'N' and proposta['novo_usado'] == 'N':
            proposta['tipo_proposta'] = 'Novo'
        elif proposta['internet'] == 'N' and proposta['novo_usado'] == 'U':
            proposta['tipo_proposta'] = 'Usado'
        elif proposta['internet'] == 'F' and proposta['novo_usado'] == 'U':
            proposta['tipo_proposta'] = 'Indefinido'
        
        query = f"""
        SELECT vop.OBSERVACAO FROM VEICULOS_OBS_PROPOSTA vop 
        WHERE 1=1
            AND vop.COD_PROPOSTA = {cod_proposta}
        """
        cur.execute(query)
        r = cur.fetchall()
        proposta['observacoes'] = []
        for row in r:
            if row[0] not in proposta['observacoes']:
                proposta['observacoes'].append(row[0])
        # converta o observacoes em string
        for obs in proposta['observacoes']:
            if obs and proposta['observacao'] and obs in proposta['observacao']:
                proposta['observacao'] = proposta['observacao'].replace(obs, '')
        # se proposta['observacao'] for vazio substitua pelo valor de observacoes
        if proposta['observacao'] is None or proposta['observacao'] == '':
            proposta['observacao'] = proposta['observacoes']
        
        query = f"""
            SELECT fp.descricao descricao_forma_pgto, 
            vfp.VALOR, vfp.OBS, vfp.COD_CLIENTE_TROCO beneficiario,
            vfp.COD_AVALIACAO
            FROM VEIC_FORMAS_PAGAMENTO vfp 
            LEFT JOIN FORMA_PGTO fp ON 1=1
                AND fp.COD_FORMA_PGTO = vfp.COD_FORMA_PGTO 
                AND fp.COD_EMPRESA = vfp.COD_EMPRESA 
            WHERE 1=1
                AND vfp.COD_PROPOSTA = '{cod_proposta}'
        """
        cur.execute(query)
        r_formas = cur.fetchall()
        proposta['formas_pagamento'] = []
        for row in r_formas:
            avaliacao = None
            if row[4]:
                query = f"""
                    SELECT 
                        fu.CHASSI_COMPLETO, 
                        fu.PLACA,
                        fu.ANO_MOD, 
                        pm.DESCRICAO_MODELO, 
                        ce.DESCRICAO cor_externa, 
                        fu.DATA_AVALIACAO, 
                        fu.data_aprovacao, 
                        eu.NOME_COMPLETO quem_avaliou,
                        fu.nome_do_cliente,
                        fu.avaliacao_sistema,
                        fu.quanto_cliente_quer,
                        fu.avaliacao_aprovada
                    FROM FU_USADOS fu
                    LEFT JOIN PRODUTOS_MODELOS pm ON 1=1
                        AND pm.COD_PRODUTO = fu.COD_PRODUTO 
                        AND pm.COD_MODELO = fu.COD_MODELO 
                    LEFT JOIN cores_externas ce ON 1=1
                        AND ce.COR_EXTERNA = fu.COR_EXTERNA 
                    LEFT JOIN EMPRESAS_USUARIOS eu ON 1=1
                        AND eu.nome = fu.QUEM_AVALIOU 
                    WHERE 1=1
                        AND fu.COD_AVALIACAO = '{row[4]}'
                """
                cur.execute(query)
                r_aval = cur.fetchall()
                if r_aval:
                    avaliacao = {
                        'chassi_completo': r_aval[0][0],
                        'placa': r_aval[0][1],
                        'ano_mod': r_aval[0][2],
                        'descricao_modelo': r_aval[0][3],
                        'cor_externa': r_aval[0][4],
                        'data_avaliacao': r_aval[0][5],
                        'data_aprovacao': r_aval[0][6],
                        'quem_avaliou': r_aval[0][7],
                        'nome_do_cliente': r_aval[0][8],
                        'avaliacao_sistema': float(r_aval[0][9]) if r_aval[0][9] else None,
                        'quanto_cliente_quer': float(r_aval[0][10]) if r_aval[0][10] else None,
                        'avaliacao_aprovada': float(r_aval[0][11]) if r_aval[0][11] else None,
                    }
            proposta['formas_pagamento'].append({
                'descricao_forma_pgto': row[0],
                'valor': float(row[1]) if row[1] else None,
                'obs': row[2],
                'beneficiario': row[3],
                'avaliacao': avaliacao
            })        
        
        cur.close()
        conn.close()
        return jsonify(proposta), 200
    
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400
        
        