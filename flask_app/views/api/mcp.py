import uuid
import json
from flask import Blueprint, jsonify, request, Response, stream_with_context
from database import oracle
from datetime import datetime, timedelta

mcp_bp = Blueprint('mcp', __name__)

def get_propostas_oracle(data_inicio=None, data_fim=None, vendedor=None):
    """Executa a consulta de propostas no Oracle filtrando por intervalo de datas (máximo 1 ano)."""
    hoje = datetime.now().strftime('%Y-%m-%d')
    
    # Suporte para parâmetro legada 'data' se data_inicio/data_fim não forem informados
    if not data_inicio and not data_fim:
        data_inicio = hoje
        data_fim = hoje
    elif data_inicio and not data_fim:
        data_fim = data_inicio
    elif data_fim and not data_inicio:
        data_inicio = data_fim

    # Validar formato e aplicar limite de 1 ano (366 dias)
    try:
        dt_ini = datetime.strptime(data_inicio, '%Y-%m-%d')
        dt_fim = datetime.strptime(data_fim, '%Y-%m-%d')
    except Exception:
        data_inicio, data_fim = hoje, hoje
        dt_ini = datetime.strptime(data_inicio, '%Y-%m-%d')
        dt_fim = datetime.strptime(data_fim, '%Y-%m-%d')

    if dt_ini > dt_fim:
        dt_ini, dt_fim = dt_fim, dt_ini
        data_inicio, data_fim = data_fim, data_inicio

    if (dt_fim - dt_ini).days > 366:
        dt_ini = dt_fim - timedelta(days=365)
        data_inicio = dt_ini.strftime('%Y-%m-%d')

    filter_vendedor = f"AND UPPER(vp.VENDEDOR) LIKE UPPER('%{vendedor}%')" if vendedor else ""

    query = f"""
    SELECT 
        vp.COD_PROPOSTA, 
        TO_CHAR(vp.EMISSAO, 'YYYY-MM-DD HH24:MI:SS') as emissao,
        c.COD_CLIENTE, 
        c.NOME as nome_cliente, 
        pm.DESCRICAO_MODELO, 
        vp.VALOR_PROPOSTA,
        cvp.ID_PROCESSO,
        vp.STATUS_PROPOSTA
    FROM veiculos_propostas vp
    LEFT JOIN EMPRESAS_USUARIOS eu ON 1=1 AND eu.NOME = vp.VENDEDOR
    LEFT JOIN PRODUTOS_MODELOS pm ON 1=1 AND pm.COD_PRODUTO = vp.COD_PRODUTO AND pm.COD_MODELO = vp.COD_MODELO 
    LEFT JOIN clientes c ON 1=1 AND c.COD_CLIENTE = vp.COD_CLIENTE 
    LEFT JOIN caiuas_veic_proc cvp ON 1=1 AND cvp.COD_PROPOSTA = vp.COD_PROPOSTA 
    WHERE 1=1
      AND vp.STATUS_PROPOSTA in ('A','V')
      AND trunc(vp.EMISSAO) BETWEEN trunc(TO_DATE('{data_inicio}', 'YYYY-MM-DD')) AND trunc(TO_DATE('{data_fim}', 'YYYY-MM-DD'))
      {filter_vendedor}
    ORDER BY vp.EMISSAO DESC
    """

    conn, cur = None, None
    try:
        conn, cur = oracle()
        cur.execute(query)
        rows = cur.fetchall() or []
        propostas = []
        for r in rows:
            st = r[7]
            status_desc = 'Aberta' if st == 'A' else ('Vendido' if st == 'V' else st)
            propostas.append({
                'cod_proposta': r[0],
                'emissao': r[1],
                'cod_cliente': r[2],
                'nome_cliente': r[3],
                'modelo': r[4],
                'valor_proposta': float(r[5]) if r[5] is not None else 0.0,
                'id_processo': r[6],
                'status_proposta': status_desc
            })
        return propostas, data_inicio, data_fim
    finally:
        if cur: cur.close()
        if conn: conn.close()


@mcp_bp.route('/api/mcp', methods=['GET', 'POST'])
def handle_mcp():
    """Endpoint único MCP: trata GET (handshake SSE) e POST (mensagens JSON-RPC e REST)."""
    # GET: Handshake do Server-Sent Events (SSE) do protocolo MCP
    if request.method == 'GET':
        session_id = str(uuid.uuid4())
        host = request.headers.get('Host', 'backend.caiuas.com.br')
        scheme = request.headers.get('X-Forwarded-Proto', request.scheme)
        msg_url = f"{scheme}://{host}/api/mcp?sessionId={session_id}"
        return Response(
            stream_with_context(iter([f"event: endpoint\ndata: {msg_url}\n\n"])),
            headers={'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache', 'Access-Control-Allow-Origin': '*'}
        )

    # POST: Processa requisições JSON-RPC (MCP) ou REST diretas
    data = request.get_json(silent=True) or {}
    method = data.get('method')
    req_id = data.get('id')

    if method == 'initialize':
        return jsonify({
            'jsonrpc': '2.0', 'id': req_id,
            'result': {
                'protocolVersion': '2024-11-05',
                'capabilities': {'tools': {}},
                'serverInfo': {'name': 'NBS', 'version': '1.0.0'}
            }
        })
    elif method in ('notifications/initialized', 'ping'):
        return jsonify({'jsonrpc': '2.0', 'id': req_id, 'result': {}}) if req_id else ('', 202)
    elif method == 'tools/list':
        return jsonify({
            'jsonrpc': '2.0', 'id': req_id,
            'result': {
                'tools': [{
                    'name': 'consultar_propostas_emitidas',
                    'description': 'Consulta propostas de veículos emitidas em um intervalo de datas (data_inicio e data_fim, com limite máximo de 1 ano). Retorna código, emissão, cliente, modelo, valor, processo e status.',
                    'inputSchema': {
                        'type': 'object',
                        'properties': {
                            'data_inicio': {'type': 'string', 'description': 'Data inicial no formato YYYY-MM-DD (ex: 2026-01-01). Obrigatória.'},
                            'data_fim': {'type': 'string', 'description': 'Data final no formato YYYY-MM-DD (ex: 2026-08-07). Limite máximo de 1 ano. Obrigatória.'},
                            'vendedor': {'type': 'string', 'description': 'Filtro por nome do vendedor (opcional).'}
                        },
                        'required': ['data_inicio', 'data_fim']
                    }
                }]
            }
        })
    elif method == 'tools/call':
        args = (data.get('params') or {}).get('arguments') or {}
        d_ini = args.get('data_inicio') or args.get('data')
        d_fim = args.get('data_fim') or args.get('data')
        propostas, dt_ini, dt_fim = get_propostas_oracle(d_ini, d_fim, args.get('vendedor'))
        txt = f"Propostas emitidas no período de {dt_ini} até {dt_fim} (Total: {len(propostas)}):\n\n" + json.dumps(propostas, ensure_ascii=False, indent=2)
        return jsonify({'jsonrpc': '2.0', 'id': req_id, 'result': {'content': [{'type': 'text', 'text': txt}]}})

    # Fallback para chamada REST direta
    d_ini = data.get('data_inicio') or data.get('data') or request.args.get('data_inicio') or request.args.get('data')
    d_fim = data.get('data_fim') or data.get('data') or request.args.get('data_fim') or request.args.get('data')
    propostas, dt_ini, dt_fim = get_propostas_oracle(d_ini, d_fim, data.get('vendedor') or request.args.get('vendedor'))
    return jsonify({'status': 'success', 'total': len(propostas), 'periodo': {'data_inicio': dt_ini, 'data_fim': dt_fim}, 'propostas': propostas}), 200