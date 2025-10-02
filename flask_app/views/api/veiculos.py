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

