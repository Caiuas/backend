from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import os
import jaydebeapi
from datetime import datetime, timedelta, timezone
from functools import wraps
from dotenv import load_dotenv
from views.api.clients import clients_bp
from views.api.reports import reports_bp
from views.api.site import site_bp
from views.api.agendamento import agendamento_bp
from views.api.dashboard import dashboard_bp
from views.api.crm import crm_bp
from views.api.veiculos import veiculos_bp
# from views.api.files import files_bp
from views.api.users import users_bp
from views.api.financeiro import financeiro_bp
from views.api.oficina import oficina_bp
from views.api.nf import nf_bp
from views.api.files import files_bp
load_dotenv()

app = Flask(__name__)
app.static_folder = 'static'
cors = CORS(app)
# static_files = /static

# register app
app.register_blueprint(clients_bp)
app.register_blueprint(reports_bp)
app.register_blueprint(site_bp)
app.register_blueprint(agendamento_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(crm_bp)
app.register_blueprint(veiculos_bp)
app.register_blueprint(users_bp)
app.register_blueprint(financeiro_bp)
app.register_blueprint(oficina_bp)
app.register_blueprint(nf_bp)
app.register_blueprint(files_bp)


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            token_parts = auth_header.split(' ')
            
            if len(token_parts) == 2 and token_parts[0] == 'Bearer':
                token = token_parts[1]

        if not token:
            return jsonify({'message': 'Usuário não autenticado!'}), 401

        try:
            fuso_horario_offset = timedelta(hours=-3)
            fuso_horario = timezone(fuso_horario_offset)
            token = jwt.decode(token, os.getenv('SECRET_KEY'), algorithms=["HS256"])
            # print(token)
            data_expiracao = datetime.fromtimestamp(token['exp'])
            agora = datetime.now(fuso_horario).timestamp()
            agora = datetime.fromtimestamp(agora)
            agora = agora.strftime('%Y-%m-%d %H:%M:%S %Z')
            if float(token['exp']) < (datetime.now(fuso_horario).timestamp()):
                return jsonify({'message': 'Token expirado!'}), 401
        except Exception as e:
            # print(e)
            return jsonify({f"message": 'Token Inválido!'}), 401

        setattr(request, 'token_data', token)  # Adiciona os dados decodificados ao objeto request

        return f(*args, **kwargs)

    return decorated

# rota de teste /
@app.route('/', methods=['GET'])
def home():
    return 'oi'
