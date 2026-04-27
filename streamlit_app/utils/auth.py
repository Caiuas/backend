import requests
import jwt
import streamlit as st
from datetime import datetime

def realizar_login(email, password):
    url = "https://app.caiuas.com.br/api/login"
    payload = {"email": email, "password": password}
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            token = response.json().get("token")
            # Salva o token na URL de forma nativa e instantânea
            st.query_params["token"] = token
            return token
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
    return None

def validar_token(token):
    try:
        # Decodifica sem validar assinatura para checar expiração localmente
        decoded = jwt.decode(token, options={"verify_signature": False})
        if datetime.now().timestamp() < decoded.get("exp"):
            return decoded
    except:
        pass
    return None

# --- LÓGICA DE PERSISTÊNCIA VIA URL (INSTANTÂNEA) ---

# Tenta pegar o token da URL
url_token = st.query_params.get("token")

if url_token:
    dados_usuario = validar_token(url_token)
    if dados_usuario:
        st.session_state.authenticated = True
        st.session_state.user_name = dados_usuario.get("name", "Usuário")
        st.session_state.user_email = dados_usuario.get("email", "")
        st.session_state.token = url_token
    else:
        # Se o token na URL expirou, limpa a URL
        st.query_params.clear()
        st.session_state.authenticated = False

