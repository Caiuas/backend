from flask import Blueprint, jsonify, request
from database import oracle, chatwoot
from dotenv import load_dotenv
from datetime import datetime
load_dotenv()

users_bp = Blueprint('users', __name__)

@users_bp.route('/api/users/users_crm', methods=['GET'])
def get_users_crm():
    try:
        conn_oracle, cur_oracle = oracle()
        query = f"""
            Select eu.nome, eu.nome_completo, ef.DESCRICAO, ef.COD_FUNCAO 
            from empresas_usuarios eu
            LEFT JOIN EMPRESAS_FUNCOES ef ON 1=1
                AND ef.COD_FUNCAO = eu.COD_FUNCAO 
            WHERE NVl(DEMITIDO,'N') = 'N'
            and eu.nome in (
                'CTSUSAN_HI',
                'LALVES_HI',
                'CTFABIO',
                'FMORAES_HS',
                'MDANTAS_HS',
                'ANGELAV_HI',
                'ANGELAV_HS',
                'EMILAN_HI',
                'FGAYA_HS',
                'FGAYA_HI',
                'KARRUDA_HS',
                'KARRUDA_HI',
                'KDIAS_HS',
                'KDIAS_HI',
                'NBS',
                'NBS_HI',
                'DALTON_HI',
                'DALTON',
                'DENISEV_H',
                'DENISE_HI'
            )
            order by eu.COD_FUNCAO, eu.nome_completo
        """
        cur_oracle.execute(query)
        rows = cur_oracle.fetchall()
        if len(rows) == 0:
            return jsonify({'status': 'error', 'message': 'Não tem usuários CRM'}), 404
        retorno = {}
        retorno['usuarios_crm'] = []
        for row in rows:
            retorno['usuarios_crm'].append({
                'nome': row[0],
                'nome_completo': row[1],
                'descricao': row[2],
                'cod_funcao': row[3]
            })
        cur_oracle.close()
        conn_oracle.close()
        return jsonify(retorno), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    