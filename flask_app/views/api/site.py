from flask import Blueprint, jsonify, request
from database import oracle, chatwoot
from dotenv import load_dotenv
load_dotenv()

site_bp = Blueprint('site', __name__)

# recebe um numero via 
@site_bp.route('/api/site/<int:cod_cliente>', methods=['GET'])
def get_site(cod_cliente):
    try:
        conn_oracle, cur_oracle = oracle()
        query = f"""
            SELECT c.COD_CLIENTE, c.NOME, c.TELEFONE_CEL 
            FROM clientes c  
            WHERE 1=1
                AND c.COD_CLIENTE = ('{cod_cliente}')
        """
        cur_oracle.execute(query)
        result_oracle = cur_oracle.fetchall()
        # cur_oracle.close()
        if len(result_oracle) == 0:
            return jsonify({'status': 'error', 'message': 'Cliente não encontrado'}), 404
        cliente = {}
        cliente['cpf_cnpj'] = result_oracle[0][0]
        cliente['nome'] = result_oracle[0][1]
        cliente['telefone'] = result_oracle[0][2]
        cliente['veiculos'] = []
        query = f"""
        SELECT cf.CHASSi, cf.PLACA, p.DESCRICAO_PRODUTO, pm.DESCRICAO_MODELO, cf.DATA_COMPRA
            FROM CLIENTES_FROTA cf 
            LEFT JOIN produtos p ON 1=1
                AND p.cod_produto = cf.cod_produto
            LEFT JOIN produtos_modelos pm ON 1=1
                AND pm.COD_PRODUTO = cf.COD_PRODUTO
                AND pm.COD_MODELO = cf.COD_MODELO
            WHERE cf.cod_cliente = ('{cod_cliente}')
        """
        cur_oracle.execute(query)
        result_oracle = cur_oracle.fetchall()
        cliente['elegible'] = True
        cliente['pontos'] = 90
        for row in result_oracle:
            veiculo = {
                'chassi': row[0],
                'placa': row[1],
                'produto': row[2],
                'modelo': row[3],
                'data_compra': str(row[4])
            }
            query = f"""
                SELECT os.numero_os, os.DATA_EMISSAO, os.DATA_ENCERRADA, os.VALOR_SERVICOS_BRUTO, os.VALOR_ITENS_BRUTO, (os.VALOR_SERVICOS_BRUTO + os.VALOR_ITENS_BRUTO) total
                FROM os_dados_veiculos 
                LEFT JOIN os ON OS.NUMERO_OS = os_dados_veiculos.NUMERO_OS
                    AND OS.COD_EMPRESA = os_dados_veiculos.COD_EMPRESA
                WHERE os_dados_veiculos.chassi = '{row[0]}'
                """
            cur_oracle.execute(query)
            result_os = cur_oracle.fetchall()
            if len(result_os) > 0:
                veiculo['os'] = []
                for os in result_os:
                    veiculo['os'].append({
                        'numero_os': os[0],
                        'data_emissao': str(os[1]),
                        'data_encerrada': str(os[2]),
                        'valor_servicos_bruto': os[3],
                        'valor_itens_bruto': os[4],
                        'total': os[5]
                    })
            else:
                veiculo['os'] = None
            cliente['veiculos'].append(veiculo)
            
        return jsonify(cliente), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400