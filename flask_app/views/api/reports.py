from flask import Blueprint, jsonify, request, Response
from database import oracle, chatwoot
from dotenv import load_dotenv
load_dotenv()

reports_bp = Blueprint('reports', __name__)

@reports_bp.route('/api/reports/crm_agenda', methods=['GET'])
def get_crm_agenda():
    conn_oracle, cur_oracle = oracle()
    query = """
    SELECT pb.COD_EMPRESA_FILTRO, cet.desc_tipo_evento, count(*)
    FROM OS_AGENDA oa 
    LEFT JOIN CRM_EVENTOS ce ON 1=1
        AND ce.COD_EMPRESA = oa.COD_EMPRESA
        AND ce.COD_EVENTO = oa.CRM_COD_EVENTO
    LEFT JOIN clientes c ON c.COD_CLIENTE = oa.COD_CLIENTE
    LEFT JOIN CRM_EVENTOS_TIPO cet ON 1=1
        AND cet.cod_tipo_evento = ce.COD_TIPO_EVENTO
    LEFT JOIN PRISMA_BOX pb ON 1=1
                AND pb.prisma = oa.PRISMA
    WHERE 1=1
        AND to_date(oa.DATA_AGENDADA) >= TO_DATE('2025-06-28', 'YYYY-MM-DD')
        AND to_date(oa.DATA_AGENDADA) <= TO_DATE('2025-06-28', 'YYYY-MM-DD')
        AND ce.TEM_CHIP_SERVICO = 'S'
    GROUP BY pb.COD_EMPRESA_FILTRO, cet.desc_tipo_evento
    ORDER BY 1, 2
    """
    cur_oracle.execute(query)
    result_oracle = cur_oracle.fetchall()
    cur_oracle.close()
    conn_oracle.close()

    # Monta HTML
    html = '''
    <html>
    <head><title>Relatório CRM Agenda</title></head>
    <body>
    <h2>Relatório CRM Agenda</h2>
    <table border="1" cellpadding="5" cellspacing="0">
        <tr>
            <th>cod_empresa_filtro</th>
            <th>desc_tipo_evento</th>
            <th>count</th>
        </tr>
    '''
    for row in result_oracle:
        html += f"""
        <tr>
            <td>{row[0]}</td>
            <td>{row[1]}</td>
            <td>{row[2]}</td>
        </tr>
        """
    html += """
    </table>
    </body>
    </html>
    """
    return Response(html, mimetype='text/html')