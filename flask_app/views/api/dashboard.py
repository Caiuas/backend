from flask import Blueprint, jsonify, request
from database import oracle, chatwoot
from dotenv import load_dotenv
from datetime import datetime
load_dotenv()

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/api/dashboard/totais', methods=['GET'])
def get_totais():
    try:
        retorno = {}
        conn_oracle, cur_oracle = oracle()
        hoje = datetime.now().strftime('%Y-%m-%d')
        query = f"""
        SELECT count(*) 
                FROM os o
                WHERE 1=1
                    and trunc(o.data_emissao) >= trunc(TO_DATE('{hoje}', 'YYYY-MM-DD'))
                    and o.complemento <> 'S'
                    AND o.ORCAMENTO <> 'S'
                    AND numero_os > 0
        """
        cur_oracle.execute(query)
        result_oracle = cur_oracle.fetchall()
        retorno['total_os'] = result_oracle[0][0]
        cur_oracle.close()
        conn_oracle.close()
        return jsonify(retorno), 200
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500