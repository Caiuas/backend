from flask import Blueprint, jsonify, request
from database import oracle, chatwoot
from dotenv import load_dotenv
load_dotenv()

clients_bp = Blueprint('clients', __name__)

@clients_bp.route('/api/clients', methods=['GET'])
def get_clients():
    retorno = {}
    conn_oracle, cur_oracle = oracle()
    query = "SELECT count(*) FROM clientes"
    cur_oracle.execute(query)
    result_oracle = cur_oracle.fetchall()
    cur_oracle.close()
    conn_oracle.close()
    retorno['status'] = 'ok'
    retorno['oracle'] = result_oracle[0][0]
    return jsonify(retorno)