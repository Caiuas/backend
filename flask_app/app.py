from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import os
import jaydebeapi
from dotenv import load_dotenv
from views.api.clients import clients_bp
from views.api.reports import reports_bp
from views.api.site import site_bp
from views.api.agendamento import agendamento_bp
from views.api.dashboard import dashboard_bp
from views.api.crm import crm_bp
from views.api.veiculos_estoque import veiculos_estoque_bp
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
app.register_blueprint(veiculos_estoque_bp)