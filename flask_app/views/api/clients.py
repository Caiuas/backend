from flask import Blueprint, jsonify, request
from database import oracle, chatwoot
from dotenv import load_dotenv
from auth import token_required
load_dotenv()

clients_bp = Blueprint('clients', __name__)

@clients_bp.route('/api/clients', methods=['GET'])
@token_required
def get_clients():
    try:
        token_data = request.token_data
        email = token_data.get('email').strip().lower()
        search = request.args.get('search', None)
        current_page = int(request.args.get('current_page', 1))
        limit = int(request.args.get('limit', 10))
        retorno = {}
        
        # Filtro de busca
        filter_search = ''
        if search:
            search = search.replace("'", "''").lower()
            filter_search = f"""
                WHERE (
                    LOWER(c.cod_cliente) LIKE '%{search}%' 
                    OR LOWER(c.nome) LIKE '%{search}%'
                    OR LOWER(concat(c.PREFIXO_RES,c.TELEFONE_RES)) LIKE '%{search}%' 
                    OR LOWER(concat(c.PREFIXO_COM,c.TELEFONE_COM)) LIKE '%{search}%'
                    OR LOWER(concat(c.PREFIXO_FAX,c.TELEFONE_FAX)) LIKE '%{search}%'
                    OR LOWER(concat(c.PREFIXO_MSG_TXT_INST,c.NUMERO_MSG_TXT_INST)) LIKE '%{search}%'
                    OR LOWER(c.ENDERECO_ELETRONICO) LIKE '%{search}%'
                    OR LOWER(c.EMAIL2) LIKE '%{search}%'
                    OR LOWER(c.EMAIL_NFE) LIKE '%{search}%'
                )
            """
        
        conn_oracle, cur_oracle = oracle()
        
        # Query para contar total de registros
        query = f"""
            SELECT COUNT(*) 
            FROM clientes c
            {filter_search}
        """
        cur_oracle.execute(query)
        total = cur_oracle.fetchone()[0]
        
        if total == 0:
            return jsonify({'status': 'error', 'message': 'Nenhum cliente encontrado'}), 404
        
        # Calcular paginação
        offset = (current_page - 1) * limit
        total_pages = (total + limit - 1) // limit
        start_row = (current_page - 1) * limit + 1
        end_row = current_page * limit
        
        if current_page > total_pages:
            return jsonify({'status': 'error', 'message': 'Página inválida'}), 400
        
        # Query para buscar dados paginados
        query = f"""
            SELECT *
            FROM (
                SELECT t.*, ROWNUM AS rn
                FROM (
                    SELECT
                        c.cod_cliente, 
                        c.NOME, 
                        concat(c.PREFIXO_RES,c.TELEFONE_RES) tel_residencial,
                        concat(c.PREFIXO_COM,c.TELEFONE_COM) tel_comercial,
                        concat(c.PREFIXO_FAX,c.TELEFONE_FAX) tel_fax,
                        concat(c.PREFIXO_MSG_TXT_INST,c.NUMERO_MSG_TXT_INST) tel_whatsapp,
                        c.ENDERECO_ELETRONICO ,
                        c.EMAIL2 ,
                        c.EMAIL_NFE ,
                        c.rua_res,
                        c.FACHADA_RES numero_res,
                        c.BAIRRO_RES,
                        c.UF_RES,
                        ci_res.DESCRICAO cidade_res,
                        c.COMPLEMENTO_RES,
                        c.CEP_RES,
                        c.rua_com,
                        c.FACHADA_COM numero_COM,
                        c.BAIRRO_COM,
                        c.UF_COM,
                        ci_COM.DESCRICAO cidade_com,
                        c.COMPLEMENTO_COM,
                        c.CEP_COM,
                        c.RUA_COBRANCA ,
                        c.FACHADA_COBRANCA numero_COBRANCA,
                        c.BAIRRO_COBRANCA,
                        c.UF_COBRANCA,
                        ci_COB.DESCRICAO cidade_cob,
                        c.COMPLEMENTO_COBRANCA,
                        c.CEP_COBRANCA
                    FROM clientes c
                    LEFT JOIN cidades ci_res ON 1=1
                        AND ci_res.cod_cidades = c.COD_CID_RES 
                        AND ci_res.UF = c.UF_RES 
                    LEFT JOIN cidades ci_com ON 1=1
                        AND ci_com.cod_cidades = c.COD_CID_COM 
                        AND ci_com.UF = c.UF_COM
                    LEFT JOIN cidades ci_cob ON 1=1
                        AND ci_cob.cod_cidades = c.COD_CID_COBRANCA 
                        AND ci_cob.UF = c.UF_COBRANCA
                    {filter_search}
                    ORDER BY c.nome
                ) t
            )
            WHERE rn BETWEEN {start_row} AND {end_row}
        """
        
        cur_oracle.execute(query)
        rows = cur_oracle.fetchall()
        
        retorno['total_clients'] = total
        retorno['total_pages'] = total_pages
        retorno['current_page'] = current_page
        retorno['clients'] = []
        
        for row in rows:
            retorno['clients'].append({
                'cod_cliente': row[0],
                'nome': row[1],
                'tel_residencial': row[2],
                'tel_comercial': row[3],
                'tel_fax': row[4],
                'tel_whatsapp': row[5],
                'email': row[6],
                'email2': row[7],
                'email_nfe': row[8],
                'endereco_residencial': {
                    'rua': row[9],
                    'numero': row[10],
                    'bairro': row[11],
                    'uf': row[12],
                    'cidade': row[13],
                    'complemento': row[14],
                    'cep': row[15]
                },
                'endereco_comercial': {
                    'rua': row[16],
                    'numero': row[17],
                    'bairro': row[18],
                    'uf': row[19],
                    'cidade': row[20],
                    'complemento': row[21],
                    'cep': row[22]
                },
                'endereco_cobranca': {
                    'rua': row[23],
                    'numero': row[24],
                    'bairro': row[25],
                    'uf': row[26],
                    'cidade': row[27],
                    'complemento': row[28],
                    'cep': row[29]
                }
            })
        
        cur_oracle.close()
        conn_oracle.close()
        
        return jsonify(retorno), 200
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
