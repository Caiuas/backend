from flask import Blueprint, jsonify, request
from database import oracle, chatwoot
from dotenv import load_dotenv
from datetime import datetime
load_dotenv()

veiculos_estoque_bp = Blueprint('veiculos_estoque', __name__)

@veiculos_estoque_bp.route('/api/veiculos/estoque', methods=['GET'])
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
