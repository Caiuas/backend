from flask import Blueprint, jsonify, request
from database import oracle, chatwoot
from dotenv import load_dotenv
from datetime import datetime
from auth import token_required
load_dotenv()

nf_bp = Blueprint('nf', __name__)

@nf_bp.route('/api/nf/list', methods=['GET'])
@token_required
def list_nfs():
    try:
        token_data = request.token_data
        current_page = request.args.get('current_page', default=1, type=int)
        limit = request.args.get('limit', default=100, type=int)
        initial_date = request.args.get('initial_date', default=None, type=str)
        final_date = request.args.get('final_date', default=None, type=str)
        cod_empresa = request.args.get('cod_empresa', default=None, type=int)
        search = request.args.get('search', default=None, type=str)
        numero_os = request.args.get('numero_os', default=None, type=str)
        conn_oracle, cur_oracle = oracle()
        
        
        query_numero_os = "" 
        if numero_os:
            numero_os = numero_os.strip()
            query_numero_os = f"""
                AND v.numero_os = '{numero_os}'
            """   
        
        query_initial_date = ""
        if initial_date:
            try:
                dt_initial = datetime.strptime(initial_date, '%Y-%m-%d')
                query_initial_date = f" AND v.emissao >= TO_DATE('{dt_initial.strftime('%Y-%m-%d')} 00:00:00', 'YYYY-MM-DD HH24:MI:SS') "
            except:
                return jsonify({'status': 'error', 'message': 'Data inicial inválida! Use o formato YYYY-MM-DD.'}), 400
        query_final_date = ""
        if final_date:
            try:
                dt_final = datetime.strptime(final_date, '%Y-%m-%d')
                query_final_date = f" AND v.emissao <= TO_DATE('{dt_final.strftime('%Y-%m-%d')} 23:59:59', 'YYYY-MM-DD HH24:MI:SS') "
            except:
                return jsonify({'status': 'error', 'message': 'Data final inválida! Use o formato YYYY-MM-DD.'}), 400
        
        query_search = ""
        if search:
            search = search.strip().lower()
            query_search = f"""
                AND (lower(c.nome) LIKE ('%{search}%') OR c.cod_cliente LIKE ('%{search}%') OR v.controle LIKE ('%{search}%'))
            """ 
        query_empresa = ""
        if cod_empresa:
            if int(cod_empresa) not in [11,33,111]:
                return jsonify({'status': 'error', 'message': 'Empresa inválida!'}), 400   
            query_empresa = f"""
                AND v.cod_empresa = {cod_empresa}
            """
            if token_data['email'] == 'flamiela@caiuas.com.br':
                query_empresa = """
                    AND v.cod_empresa = 11
                """
        
        query = f"""
            select count(*)
            FROM vendas v
            LEFT JOIN clientes c ON 1=1
                AND c.cod_cliente = v.cod_cliente
            WHERE 1=1
                {query_empresa}
                {query_initial_date}
                {query_final_date}
                {query_numero_os}
                AND v.serie IN ('5','3','NF')
                {query_search}
        """
        # return query
        cur_oracle.execute(query)
        total = cur_oracle.fetchone()[0]
        total_pages = (total + limit - 1) // limit
        start_row = (current_page - 1) * limit + 1
        end_row = current_page * limit
        if total == 0:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({}), 204
        retorno = {}
        retorno['total'] = total
        retorno['total_pages'] = total_pages
        retorno['current_page'] = current_page
        retorno['nfs'] = []
        query = f"""
        SELECT *
                FROM (
                    SELECT t.*, ROWNUM AS rn
                    FROM (
                        -- Sua query original com ORDER BY aqui dentro
            SELECT 
                v.cod_empresa, 
                v.controle, 
                v.serie, 
                c.cod_cliente, 
                c.nome, 
                TO_CHAR(v.emissao, 'YYYY-MM-DD HH24:MI:SS') ,
                v.total_nota
            FROM vendas v
            LEFT JOIN clientes c ON 1=1
                AND c.cod_cliente = v.cod_cliente
            WHERE 1=1
                {query_empresa}
                {query_initial_date}
                {query_final_date}
                {query_numero_os}
                AND v.serie IN ('5','3','NF')
                {query_search}
            ORDER BY c.cod_cliente, v.controle DESC
            ) t 
                )
                WHERE 
                    rn BETWEEN {start_row} AND {end_row}
        """
        cur_oracle.execute(query)
        r = cur_oracle.fetchall()
        
        for row in r:
            nf = {
                'cod_empresa': row[0],
                'controle': row[1],
                'serie': row[2],
                'cod_cliente': row[3],
                'nome_cliente': row[4],
                'emissao': row[5],
                'total_nota': float(row[6]) if row[6] else 0.0
            }
            if nf['emissao']:
                if hasattr(nf['emissao'], 'isoformat'):
                    nf['emissao'] = nf['emissao'].isoformat()
                elif isinstance(nf['emissao'], str):
                    try:
                        dt = datetime.strptime(nf['emissao'], '%Y-%m-%d %H:%M:%S')
                        nf['emissao'] = dt.isoformat()
                    except:
                        nf['emissao'] = str(nf['emissao'])
            retorno['nfs'].append(nf)
        
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

@nf_bp.route('/api/nf/download/xml/<controle>', methods=['GET'])
@token_required
def download_nf_xml(controle):
    try:
        controle = str(controle).strip().upper()
        controle, serie, empresa = controle.split('-')
        conn_oracle, cur_oracle = oracle()
        query = f"""
            SELECT count(*) FROM vendas v 
            WHERE 1=1
                AND v.CONTROLE = '{controle}'
                AND v.SERIE = '{serie}'
                AND v.cod_empresa = '{empresa}'
        """
        cur_oracle.execute(query)
        total = cur_oracle.fetchone()[0]
        if total == 0:
            cur_oracle.close()
            conn_oracle.close()
            return jsonify({'status': 'error', 'message': 'Nota fiscal não encontrada!'}), 400
        if serie == 'NF':
            query = f"""
                SELECT xml_envio FROM NFSE_MOVIMENTO nm 
                WHERE nm.ID_EMPRESA = {empresa}
                AND nm.numero_rps = {controle}
                AND nm.serie_rps = '{serie}'
            """
            cur_oracle.execute(query)
            r = cur_oracle.fetchall()
            if len(r) == 0:
                cur_oracle.close()
                conn_oracle.close()
                return jsonify({'status': 'error', 'message': 'XML da Nota Fiscal não encontrado!'}), 400
            clob = r[0][0]
            if clob:
                try:
                    # No JayDeBeApi/JDBC, o CLOB é um objeto Java.
                    # Usamos o método getSubString(posicao_inicial, tamanho)
                    # O índice no Java começa em 1.
                    xml_data = clob.getSubString(1, int(clob.length()))
                except Exception as e:
                    # Fallback caso não seja um objeto Java CLOB padrão
                    xml_data = str(clob)
            
            # retorna o arquivo para download
            cur_oracle.close()
            conn_oracle.close()
            return (xml_data, 200, {
                'Content-Type': 'application/xml',
                'Content-Disposition': f'attachment; filename=NFSE_{controle}_{serie}_{empresa}.xml'
            })
        else:
            query = f"""
                SELECT nm.xml_nota FROM nfe_movimento nm
                WHERE 1=1
                    AND nm.numr_controle = '{controle}'
                    AND nm.serie_nfe = '{serie}'
                    AND nm.id_empresa = '{empresa}'
            """
            cur_oracle.execute(query)
            r = cur_oracle.fetchall()
            if len(r) == 0:
                cur_oracle.close()
                conn_oracle.close()
                return jsonify({'status': 'error', 'message': 'XML da Nota Fiscal não encontrado!'}), 400
            clob = r[0][0]
            if clob:
                try:
                    # No JayDeBeApi/JDBC, o CLOB é um objeto Java.
                    # Usamos o método getSubString(posicao_inicial, tamanho)
                    # O índice no Java começa em 1.
                    xml_data = clob.getSubString(1, int(clob.length()))
                except Exception as e:
                    # Fallback caso não seja um objeto Java CLOB padrão
                    xml_data = str(clob)
            return (xml_data, 200, {
                'Content-Type': 'application/xml',
                'Content-Disposition': f'attachment; filename=NFE_{controle}_{serie}_{empresa}.xml'
            })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400
