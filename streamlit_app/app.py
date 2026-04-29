import streamlit as st
import requests
import jwt
from datetime import datetime
import plotly.express as px
from database import oracle, chatwoot
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import unicodedata
import io
import xlsxwriter
import extra_streamlit_components as stx
import os
import bcrypt
import pytz
import plotly.graph_objects as go

from utils.config import *
from views.recepcao import EMAILS_RECEPCAO
from views.fluxo_de_loja import EMAILS_CRM_SHOWROOM
from views.inicio import EMAILS_INICIO
from views.veiculos import EMAILS_VEICULOS
from views.estoque_de_pecas import EMAILS_ESTOQUE_PECAS
from views.obsolescencia_de_estoque import EMAILS_OBSOLESCENCIA_ESTOQUE
from views.crm import EMAILS_CRM
from views.base_clientes_veiculos import EMAILS_BASE_CLIENTES
from views.leads import EMAILS_HAMADA
from views.leads_agencia import EMAILS_CHAT
from views.leads_escalera import EMAILS_ESCALERA
from views.acompanhamento_chat import EMAILS_ACOMPANHAMENTO_CHAT
from views.acompanhamento_pos_vendas import EMAILS_POS_VENDAS
from views.acompanhamento_diario import EMAILS_ACOMPANHAMENTO_DIARIO
from views.propostas import EMAILS_PRPOSTAS
from views.fechamento_mes import EMAILS_FECHAMENTO_MES
from utils.auth import realizar_login, validar_token, check_authentication
from views import inicio
from views import estoque_de_pecas
from views import obsolescencia_de_estoque
from views import crm
from views import fluxo_de_loja
from views import recepcao
from views import veiculos
from views import base_clientes_veiculos
from views import leads
from views import leads_agencia
from views import leads_escalera
from views import acompanhamento_chat
from views import acompanhamento_pos_vendas
from views import acompanhamento_diario
from views import propostas
from views import fechamento_mes

# 1. Configuração da página
st.set_page_config(page_title="Caiuás - Acesso Rápido",layout="wide")

st.markdown("""
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)
# ---------------------------------------------------------------------------
# 2. Controle de acesso por menu
# pablo.ti@caiuas.com.br tem acesso a tudo automaticamente.
# Para liberar outros usuários, adicione o e-mail na lista correspondente.
# ---------------------------------------------------------------------------
# --- INTERFACE ---
check_authentication()

if not st.session_state.get("authenticated"):
    col_logo_l, col_logo_c, col_logo_r = st.columns([2, 1, 2])
    with col_logo_c:
        st.image("logo.png", width=200)
    st.markdown("<h1 style='text-align: center;'>Acesso ao Sistema</h1>", unsafe_allow_html=True)
    
    
    with st.form("login_form"):
        email = st.text_input("E-mail")
        password = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar", width="stretch"):
            token = realizar_login(email, password)
            if token:
                st.rerun()
            else:
                st.error("Credenciais inválidas ou erro no servidor.")
else:
    email_usuario = st.session_state.get("user_email", "")

    menus_disponiveis = []
    if tem_acesso(email_usuario, EMAILS_RECEPCAO):
        menus_disponiveis.append("RECEPCAO")
    if tem_acesso(email_usuario, EMAILS_CRM_SHOWROOM):
        menus_disponiveis.append("Fluxo de loja")
    if tem_acesso(email_usuario, EMAILS_INICIO):
        menus_disponiveis.append("inicio")
    if tem_acesso(email_usuario, EMAILS_VEICULOS):
        menus_disponiveis.append("Veículos")
    if tem_acesso(email_usuario, EMAILS_ESTOQUE_PECAS):
        menus_disponiveis.append("Estoque de peças")
    if tem_acesso(email_usuario, EMAILS_OBSOLESCENCIA_ESTOQUE):
        menus_disponiveis.append("Obsolescência de estoque")
    if tem_acesso(email_usuario, EMAILS_CRM):
        menus_disponiveis.append("CRM")
    if tem_acesso(email_usuario, EMAILS_BASE_CLIENTES):
        menus_disponiveis.append("Base Clientes/Veículos")
    if tem_acesso(email_usuario, EMAILS_HAMADA):
        menus_disponiveis.append("Leads")
    if tem_acesso(email_usuario, EMAILS_CHAT):
        menus_disponiveis.append("Leads Agência")
    if tem_acesso(email_usuario, EMAILS_ESCALERA):
        menus_disponiveis.append("Leads Escalera")
    if tem_acesso(email_usuario, EMAILS_ACOMPANHAMENTO_CHAT):
        menus_disponiveis.append("Acompanhamento Chat")
    if tem_acesso(email_usuario, EMAILS_POS_VENDAS):
        menus_disponiveis.append("Acompanhamento Pós Vendas")
    if tem_acesso(email_usuario, EMAILS_ACOMPANHAMENTO_DIARIO):
        menus_disponiveis.append("Acompanhamento Diário")
    if tem_acesso(email_usuario, EMAILS_PRPOSTAS):
        menus_disponiveis.append("Propostas")
    if tem_acesso(email_usuario, EMAILS_FECHAMENTO_MES):
        menus_disponiveis.append("Fechamento Mês")

    if not menus_disponiveis:
        st.warning("Seu usuário não possui acesso a nenhum menu. Entre em contato com o administrador.")
        if st.button("Sair"):
            st.query_params.clear()
            st.session_state.clear()
            st.rerun()
        st.stop()

    st.sidebar.image("logo.png", use_container_width=True)
    menu = st.sidebar.radio(
        "Menu",
        menus_disponiveis
    )

    menu_handlers = {
        "inicio": inicio.render,
        "Estoque de peças": estoque_de_pecas.render,
        "Obsolescência de estoque": obsolescencia_de_estoque.render,
        "CRM": crm.render,
        "Fluxo de loja": fluxo_de_loja.render,
        "RECEPCAO": recepcao.render,
        "Veículos": veiculos.render,
        "Base Clientes/Veículos": base_clientes_veiculos.render,
        "Leads": leads.render,
        "Leads Agência": leads_agencia.render,
        "Leads Escalera": leads_escalera.render,
        "Acompanhamento Chat": acompanhamento_chat.render,
        "Acompanhamento Pós Vendas": acompanhamento_pos_vendas.render,
        "Acompanhamento Diário": acompanhamento_diario.render,
        "Propostas": propostas.render,
        "Fechamento Mês": fechamento_mes.render,
    }

    if menu in menu_handlers:
        menu_handlers[menu]()

    if st.sidebar.button("Sair", width="stretch"):
        st.query_params.clear()
        st.session_state.clear()
        st.rerun()
