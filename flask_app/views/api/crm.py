from flask import Blueprint, jsonify, request
from database import oracle, chatwoot
from dotenv import load_dotenv
from datetime import datetime
load_dotenv()

crm_bp = Blueprint('crm', __name__)

@crm_bp.route('/api/eventos_atrasados', methods=['GET'])
def get_eventos_atrasados():
    try:
        conn_oracle, cur_oracle = oracle()
        retorno = {}
        now  = datetime.now().strftime("%Y-%m-%d")
        
        query = f"""
            SELECT 
            cg.cod_grupo, 
            cg.desc_grupo, 
            cet.COD_TIPO_EVENTO, 
            cet.DESC_TIPO_EVENTO, 
            count(*) eventos,
            ROUND(RATIO_TO_REPORT(COUNT(*)) OVER () * 100, 2) AS percentual
        FROM crm_eventos ce
        LEFT JOIN CRM_EVENTOS_TIPO cet ON 1=1
            AND cet.COD_TIPO_EVENTO = ce.COD_TIPO_EVENTO
        LEFT JOIN CRM_GRUPO cg ON 1=1
            AND cg.COD_GRUPO = cet.COD_GRUPO 
        WHERE 1=1
            AND ce.COD_EMPRESA IN (11,33)
            AND ce.status <> 'E' 
            and ce.status <> 'D'
            AND TRUNC(
                    CASE
                        WHEN ce.data_novo_contato IS NULL
                        THEN ce.data_evento
                        ELSE ce.data_novo_contato
                    END
                    ) < TO_DATE('{now}', 'YYYY-MM-DD')
        GROUP BY cg.cod_grupo, cg.desc_grupo, cet.COD_TIPO_EVENTO, cet.DESC_TIPO_EVENTO 
        ORDER BY 2
        """
        cur_oracle.execute(query)
        rows = cur_oracle.fetchall()
        if len(rows) == 0:
            return jsonify({'status': 'error', 'message': 'Não tem eventos pendentes'}), 404
        retorno['eventos_pendentes'] = []
        for row in rows:
            retorno['eventos_pendentes'].append({
                'cod_grupo': row[0],
                'desc_grupo': row[1],
                'cod_tipo_evento': row[2],
                'desc_tipo_evento': row[3],
                'eventos': row[4],
                'percentual': float(row[5])
            })
        cur_oracle.close()
        conn_oracle.close()
        return jsonify(retorno), 200
            
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@crm_bp.route('/api/crm_andamentos', methods=['GET'])
def get_crm_andamentos():
    try:
        return 'oi'
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
        