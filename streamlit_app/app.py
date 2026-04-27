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

# 1. Configuração da página
st.set_page_config(page_title="Caiuás - Acesso Rápido",layout="wide")

# ---------------------------------------------------------------------------
# 2. Controle de acesso por menu
# pablo.ti@caiuas.com.br tem acesso a tudo automaticamente.
# Para liberar outros usuários, adicione o e-mail na lista correspondente.
# ---------------------------------------------------------------------------

EMAIL_ADMIN = "pablo.ti@caiuas.com.br"

EMAILS_RECEPCAO = [
    "pablo.ti@caiuas.com.br",
    "mirela.novaga@caiuas.com.br",
    "Isadora.fraga@caiuas.com.br"
]

EMAILS_CRM_SHOWROOM = [
    "pablo.ti@caiuas.com.br",
    "cristiane.aguilar@caiuas.com.br",
    "cristiane.aguilar@caiuas.com.br",
    "franciele.mayer@caiuas.com.br"
]

EMAILS_INICIO = [
    "pablo.ti@caiuas.com.br",
]

EMAILS_VEICULOS = [
    "pablo.ti@caiuas.com.br",
]

EMAILS_ESTOQUE_PECAS = [
    "pablo.ti@caiuas.com.br",
]

EMAILS_OBSOLESCENCIA_ESTOQUE = [
    "pablo.ti@caiuas.com.br",
]

EMAILS_CRM = [
    "pablo.ti@caiuas.com.br"
]

EMAILS_BASE_CLIENTES = [
    "pablo.ti@caiuas.com.br",
]

EMAILS_IMPLANTACAO = [
    "pablo.ti@caiuas.com.br",
]

EMAILS_HAMADA = [
    "pablo.ti@caiuas.com.br",
    "cristiane.aguilar@caiuas.com.br",
    "marcelotcf@caiuas.com.br"
]

EMAILS_CHAT = [
    "pablo.ti@caiuas.com.br",
    "cristiane.aguilar@caiuas.com.br",
    "marcelotcf@caiuas.com.br",
    "rafael@escaleraconsultoria.com.br"
]

EMAILS_ESCALERA = [
    "pablo.ti@caiuas.com.br",
    "rafael@escaleraconsultoria.com.br"
]

EMAILS_ACOMPANHAMENTO_CHAT = [
    "pablo.ti@caiuas.com.br",
]

EMAILS_POS_VENDAS = [
    "pablo.ti@caiuas.com.br",
    "cristiane.aguilar@caiuas.com.br"
]

EMAILS_ACOMPANHAMENTO_DIARIO = [
    "pablo.ti@caiuas.com.br",
    "marcelotcf@caiuas.com.br",
    "duda@pantys.com.br"
]

def tem_acesso(email_usuario, lista_emails):
    """Retorna True se o e-mail é admin ou está na lista do menu."""
    return email_usuario == EMAIL_ADMIN or email_usuario in lista_emails

# 2. Funções de Autenticação
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

# --- INTERFACE ---

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
    if tem_acesso(email_usuario, EMAILS_IMPLANTACAO):
        menus_disponiveis.append("IMPLANTACAO")
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
    
    if menu == "inicio":
        st.title("BI - Caiuás")
        st.write("Bem-vindo ao dashboard de BI da Caiuás!")
        st.write("Use o menu lateral para navegar entre as diferentes seções.")
        
    if menu == "Estoque de peças":
        st.title("Acompanhamento de estoque")
        query = f"""
        SELECT 
            em.nome, igi.DESCRICAO,
            sum(e.QTDE) quantidade,
            sum((e.QTDE * ic.CUSTO_CONTABIL)) custo
            FROM estoque e
            LEFT JOIN itens i ON 1=1
                AND i.cod_item = e.cod_item
            LEFT JOIN ITENS_GRUPO_INTERNO igi ON 1=1
                AND igi.COD_GRUPO_INTERNO = i.COD_GRUPO_INTERNO
            LEFT JOIN ITENS_FORNECEDOR if2 ON 1=1
                AND if2.COD_ITEM = e.COD_ITEM
                AND if2.COD_FORNECEDOR = e.COD_FORNECEDOR
            LEFT JOIN empresas em ON 1=1
                AND em.COD_EMPRESA = e.COD_EMPRESA
            LEFT JOIN itens_custos ic ON 1=1
                AND ic.cod_item = i.COD_ITEM
                AND ic.COD_FORNECEDOR = e.COD_FORNECEDOR
                AND ic.COD_EMPRESA = e.COD_EMPRESA
            WHERE 1=1
                AND e.QTDE > 0
            GROUP BY em.nome, igi.DESCRICAO
            ORDER BY 1,2
        """
        conn_oracle, cur_oracle = oracle()
        cur_oracle.execute(query)
        result_oracle = cur_oracle.fetchall()
        result = pd.DataFrame(result_oracle, columns=["Empresa", "Grupo Interno", "Quantidade", "Custo Contabil"], dtype=str)
        result["Quantidade"] = result["Quantidade"].astype(float)
        result["Custo Contabil"] = result["Custo Contabil"].astype(float)
        # Filtros na barra lateral
        empresas = result["Empresa"].unique()
        empresa_selecionada = st.sidebar.selectbox("Filtrar por empresa", ["Todas"] + list(empresas))
        grupos = result["Grupo Interno"].unique()
        grupo_selecionado = st.sidebar.selectbox("Filtrar por grupo interno", ["Todos"] + list(grupos))
        # Aplicando os filtros
        df_filtrado = result.copy()
        if empresa_selecionada != "Todas":
            df_filtrado = df_filtrado[df_filtrado["Empresa"] == empresa_selecionada]
        if grupo_selecionado != "Todos":
            df_filtrado = df_filtrado[df_filtrado["Grupo Interno"] == grupo_selecionado]
        # Tabela total por empresa (considerando filtro)
        total_por_empresa = pd.pivot_table(
            df_filtrado,
            index=["Empresa"],
            values=["Quantidade", "Custo Contabil"],
            aggfunc={"Quantidade": "sum", "Custo Contabil": "sum"}
        ).reset_index()
        valor_estoque_total = total_por_empresa["Custo Contabil"].sum()
        # Formatação
        df_filtrado["Custo Contabil"] = df_filtrado["Custo Contabil"].apply(lambda x: f"R$ {float(x):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
        total_por_empresa["Custo Contabil"] = total_por_empresa["Custo Contabil"].apply(lambda x: f"R$ {float(x):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
        cur_oracle.close()
        conn_oracle.close()
        st.write(f"**Data de atualização: {datetime.now()}**")
        st.dataframe(df_filtrado, hide_index=True)
        st.write("**Total por empresa**")
        st.write(f"**Valor total do estoque: R$ {valor_estoque_total:,.2f}**")
        st.dataframe(total_por_empresa[["Empresa","Quantidade","Custo Contabil"]], hide_index=True)
        
    if menu == "Obsolescência de estoque":
        st.title("Obsolescência de estoque")
        query = f"""
            SELECT 
                em.nome, 
                vi.cod_item ,
                igi.DESCRICAO grupo_interno,
                i.DESCRICAO descricao_item,
                sum(vi.QTDE) QTDE,
                sum((vi.PRECO_LIQUIDO_FINAL)) valor_liquido,
                sum((vi.QTDE * vi.PRECO_UNITARIO)) valor_bruto
            FROM venda_itens vi
            LEFT JOIN empresas em ON 1=1
                AND em.COD_EMPRESA = vi.COD_EMPRESA
            LEFT JOIN vendas v ON 1=1
                AND v.cod_empresa = vi.cod_empresa
                AND v.controle = vi.CONTROLE
            LEFT JOIN OPERACOES o ON 1=1
                AND o.COD_OPERACAO = v.COD_OPERACAO
                AND v.cod_empresa = o.COD_EMPRESA
            LEFT JOIN itens i ON 1=1
                AND i.cod_item = vi.cod_item
            LEFT JOIN ITENS_GRUPO_INTERNO igi ON 1=1
                AND igi.COD_GRUPO_INTERNO = i.COD_GRUPO_INTERNO
            LEFT JOIN ITENS_FORNECEDOR if2 ON 1=1
                AND if2.COD_ITEM = vi.COD_ITEM
                AND if2.COD_FORNECEDOR = vi.COD_FORNECEDOR
            LEFT JOIN empresas em ON 1=1
                AND em.COD_EMPRESA = vi.COD_EMPRESA
            LEFT JOIN itens_custos ic ON 1=1
                AND ic.cod_item = i.COD_ITEM
                AND ic.COD_FORNECEDOR = vi.COD_FORNECEDOR
                AND ic.COD_EMPRESA = vi.COD_EMPRESA
            LEFT JOIN NFE_MOVIMENTO nm ON 1=1
                AND nm.ID_EMPRESA = v.COD_EMPRESA
                AND nm.serie_nbs = v.serie
                AND nm.numr_controle = v.controle
            WHERE 1=1
                AND v.emissao BETWEEN SYSDATE - 90 AND SYSDATE
                AND v.SERIE  IN ('3','5')
                AND nm.status_nfe = 10
                AND v.COD_OPERACAO IN (1,2,3,10,19,26,34)
                GROUP BY 
                em.nome,
                vi.cod_item ,
                igi.DESCRICAO,
                i.DESCRICAO
        """
        conn_oracle, cur_oracle = oracle()
        cur_oracle.execute(query)
        result_oracle = cur_oracle.fetchall()
        faturamento_90_dias = pd.DataFrame(result_oracle, columns=[
            "Empresa", "cod_item", "Grupo Interno", "Descrição Item",
            "Quantidade", "Valor Líquido", "Valor Bruto"
        ], dtype=str)
        faturamento_90_dias["Quantidade"] = faturamento_90_dias["Quantidade"].astype(float)
        faturamento_90_dias["Valor Líquido"] = faturamento_90_dias["Valor Líquido"].astype(float)
        faturamento_90_dias["Valor Bruto"] = faturamento_90_dias["Valor Bruto"].astype(float)
        
        query = f"""
            SELECT 
                em.nome, 
                vi.cod_item ,
                igi.DESCRICAO grupo_interno,
                i.DESCRICAO descricao_item,
                sum(vi.QTDE) QTDE,
                sum((vi.PRECO_LIQUIDO_FINAL)) valor_liquido,
                sum((vi.QTDE * vi.PRECO_UNITARIO)) valor_bruto
            FROM venda_itens vi
            LEFT JOIN empresas em ON 1=1
                AND em.COD_EMPRESA = vi.COD_EMPRESA
            LEFT JOIN vendas v ON 1=1
                AND v.cod_empresa = vi.cod_empresa
                AND v.controle = vi.CONTROLE
            LEFT JOIN OPERACOES o ON 1=1
                AND o.COD_OPERACAO = v.COD_OPERACAO
                AND v.cod_empresa = o.COD_EMPRESA
            LEFT JOIN itens i ON 1=1
                AND i.cod_item = vi.cod_item
            LEFT JOIN ITENS_GRUPO_INTERNO igi ON 1=1
                AND igi.COD_GRUPO_INTERNO = i.COD_GRUPO_INTERNO
            LEFT JOIN ITENS_FORNECEDOR if2 ON 1=1
                AND if2.COD_ITEM = vi.COD_ITEM
                AND if2.COD_FORNECEDOR = vi.COD_FORNECEDOR
            LEFT JOIN empresas em ON 1=1
                AND em.COD_EMPRESA = vi.COD_EMPRESA
            LEFT JOIN itens_custos ic ON 1=1
                AND ic.cod_item = i.COD_ITEM
                AND ic.COD_FORNECEDOR = vi.COD_FORNECEDOR
                AND ic.COD_EMPRESA = vi.COD_EMPRESA
            LEFT JOIN NFE_MOVIMENTO nm ON 1=1
                AND nm.ID_EMPRESA = v.COD_EMPRESA
                AND nm.serie_nbs = v.serie
                AND nm.numr_controle = v.controle
            WHERE 1=1
                AND v.emissao BETWEEN SYSDATE - 180 AND SYSDATE
                AND v.SERIE  IN ('3','5')
                AND nm.status_nfe = 10
                AND v.COD_OPERACAO IN (1,2,3,10,19,26,34)
                GROUP BY 
                em.nome,
                vi.cod_item ,
                igi.DESCRICAO,
                i.DESCRICAO
        """
        cur_oracle.execute(query)
        result_oracle = cur_oracle.fetchall()
        faturamento_180_dias = pd.DataFrame(result_oracle, columns=[
            "Empresa", "cod_item", "Grupo Interno", "Descrição Item",
            "Quantidade", "Valor Líquido", "Valor Bruto"
        ], dtype=str)
        faturamento_180_dias["Quantidade"] = faturamento_180_dias["Quantidade"].astype(float)
        faturamento_180_dias["Valor Líquido"] = faturamento_180_dias["Valor Líquido"].astype(float)
        faturamento_180_dias["Valor Bruto"] = faturamento_180_dias["Valor Bruto"].astype(float)
        
        query = f"""
            SELECT 
                em.nome, 
                vi.cod_item ,
                igi.DESCRICAO grupo_interno,
                i.DESCRICAO descricao_item,
                sum(vi.QTDE) QTDE,
                sum((vi.PRECO_LIQUIDO_FINAL)) valor_liquido,
                sum((vi.QTDE * vi.PRECO_UNITARIO)) valor_bruto
            FROM venda_itens vi
            LEFT JOIN empresas em ON 1=1
                AND em.COD_EMPRESA = vi.COD_EMPRESA
            LEFT JOIN vendas v ON 1=1
                AND v.cod_empresa = vi.cod_empresa
                AND v.controle = vi.CONTROLE
            LEFT JOIN OPERACOES o ON 1=1
                AND o.COD_OPERACAO = v.COD_OPERACAO
                AND v.cod_empresa = o.COD_EMPRESA
            LEFT JOIN itens i ON 1=1
                AND i.cod_item = vi.cod_item
            LEFT JOIN ITENS_GRUPO_INTERNO igi ON 1=1
                AND igi.COD_GRUPO_INTERNO = i.COD_GRUPO_INTERNO
            LEFT JOIN ITENS_FORNECEDOR if2 ON 1=1
                AND if2.COD_ITEM = vi.COD_ITEM
                AND if2.COD_FORNECEDOR = vi.COD_FORNECEDOR
            LEFT JOIN empresas em ON 1=1
                AND em.COD_EMPRESA = vi.COD_EMPRESA
            LEFT JOIN itens_custos ic ON 1=1
                AND ic.cod_item = i.COD_ITEM
                AND ic.COD_FORNECEDOR = vi.COD_FORNECEDOR
                AND ic.COD_EMPRESA = vi.COD_EMPRESA
            LEFT JOIN NFE_MOVIMENTO nm ON 1=1
                AND nm.ID_EMPRESA = v.COD_EMPRESA
                AND nm.serie_nbs = v.serie
                AND nm.numr_controle = v.controle
            WHERE 1=1
                AND v.emissao BETWEEN SYSDATE - 365 AND SYSDATE
                AND v.SERIE  IN ('3','5')
                AND nm.status_nfe = 10
                AND v.COD_OPERACAO IN (1,2,3,10,19,26,34)
                GROUP BY 
                em.nome,
                vi.cod_item ,
                igi.DESCRICAO,
                i.DESCRICAO
        """
        cur_oracle.execute(query)
        result_oracle = cur_oracle.fetchall()
        faturamento_360_dias = pd.DataFrame(result_oracle, columns=[
            "Empresa", "cod_item", "Grupo Interno", "Descrição Item",
            "Quantidade", "Valor Líquido", "Valor Bruto"
        ], dtype=str)
        faturamento_360_dias["Quantidade"] = faturamento_360_dias["Quantidade"].astype(float)
        faturamento_360_dias["Valor Líquido"] = faturamento_360_dias["Valor Líquido"].astype(float)
        faturamento_360_dias["Valor Bruto"] = faturamento_360_dias["Valor Bruto"].astype(float)
        
        query = f"""
        SELECT 
            em.nome, igi.DESCRICAO,
            i.COD_ITEM,
            sum(e.QTDE) quantidade,
            sum((e.QTDE * ic.CUSTO_CONTABIL)) custo
            FROM estoque e
            LEFT JOIN itens i ON 1=1
                AND i.cod_item = e.cod_item
            LEFT JOIN ITENS_GRUPO_INTERNO igi ON 1=1
                AND igi.COD_GRUPO_INTERNO = i.COD_GRUPO_INTERNO
            LEFT JOIN ITENS_FORNECEDOR if2 ON 1=1
                AND if2.COD_ITEM = e.COD_ITEM
                AND if2.COD_FORNECEDOR = e.COD_FORNECEDOR
            LEFT JOIN empresas em ON 1=1
                AND em.COD_EMPRESA = e.COD_EMPRESA
            LEFT JOIN itens_custos ic ON 1=1
                AND ic.cod_item = i.COD_ITEM
                AND ic.COD_FORNECEDOR = e.COD_FORNECEDOR
                AND ic.COD_EMPRESA = e.COD_EMPRESA
            WHERE 1=1
                AND e.QTDE > 0
            GROUP BY em.nome, igi.DESCRICAO, i.cod_item
            ORDER BY 1,2
        """
        cur_oracle.execute(query)
        result_oracle = cur_oracle.fetchall()
        estoque = pd.DataFrame(result_oracle, columns=["Empresa", "Grupo Interno","cod_item", "quantidade_estoque", "Custo Contabil"], dtype=str)
        estoque["quantidade_estoque"] = estoque["quantidade_estoque"].astype(float)
        estoque["Custo Contabil"] = estoque["Custo Contabil"].astype(float)
        
        itens_sem_faturamento_90 = pd.merge(estoque, 
            faturamento_90_dias,
            on=["Empresa", "Grupo Interno", "cod_item"],
            how="left")
        itens_sem_faturamento_90['Quantidade'] = itens_sem_faturamento_90['Quantidade'].fillna(0).astype(float)
        itens_sem_faturamento_90 = itens_sem_faturamento_90[itens_sem_faturamento_90['Quantidade'] == 0]
        
        itens_sem_faturamento_180 = pd.merge(estoque, 
            faturamento_180_dias,
            on=["Empresa", "Grupo Interno", "cod_item"],
            how="left")
        itens_sem_faturamento_180['Quantidade'] = itens_sem_faturamento_180['Quantidade'].fillna(0).astype(float)
        itens_sem_faturamento_180 = itens_sem_faturamento_180[itens_sem_faturamento_180['Quantidade'] == 0]
        
        itens_sem_faturamento_360 = pd.merge(estoque, 
            faturamento_360_dias,
            on=["Empresa", "Grupo Interno", "cod_item"],
            how="left")
        itens_sem_faturamento_360['Quantidade'] = itens_sem_faturamento_360['Quantidade'].fillna(0).astype(float)
        itens_sem_faturamento_360 = itens_sem_faturamento_90[itens_sem_faturamento_360['Quantidade'] == 0]
        
        # Filtro por empresa
        empresas = pd.concat([itens_sem_faturamento_90["Empresa"], itens_sem_faturamento_360["Empresa"], itens_sem_faturamento_180["Empresa"]]).unique()
        empresa_selecionada = st.sidebar.selectbox("Filtrar por empresa", ["Todas"] + list(empresas))
        grupos = pd.concat([itens_sem_faturamento_90["Grupo Interno"], itens_sem_faturamento_360["Grupo Interno"], itens_sem_faturamento_180["Empresa"]]).unique()
        grupo_selecionado = st.sidebar.selectbox("Filtrar por grupo interno", ["Todos"] + list(grupos))
        
        # Aplicando os filtros
        df_filtrado_90 = itens_sem_faturamento_90.copy()
        df_filtrado_360 = itens_sem_faturamento_360.copy()
        df_filtrado_180 = itens_sem_faturamento_180.copy()
        if empresa_selecionada != "Todas":
            df_filtrado_90 = df_filtrado_90[df_filtrado_90["Empresa"] == empresa_selecionada]
            df_filtrado_180 = df_filtrado_180[df_filtrado_180["Empresa"] == empresa_selecionada]
            df_filtrado_360 = df_filtrado_360[df_filtrado_360["Empresa"] == empresa_selecionada]
        
        if grupo_selecionado != "Todos":
            df_filtrado_90 = df_filtrado_90[df_filtrado_90["Grupo Interno"] == grupo_selecionado]
            df_filtrado_180 = df_filtrado_180[df_filtrado_180["Grupo Interno"] == grupo_selecionado]
            df_filtrado_360 = df_filtrado_360[df_filtrado_360["Grupo Interno"] == grupo_selecionado]
        
        valor_total_estoque_90 = df_filtrado_90["Custo Contabil"].sum()    
        valor_total_estoque_180 = df_filtrado_180["Custo Contabil"].sum()
        valor_total_estoque_360 = df_filtrado_360["Custo Contabil"].sum()
        
        itens_sem_faturamento_90 = itens_sem_faturamento_90[['Empresa', 'Grupo Interno', 'cod_item', 'quantidade_estoque', 'Custo Contabil']]
        itens_sem_faturamento_90['Custo Contabil'] = itens_sem_faturamento_90['Custo Contabil'].apply(lambda x: f"R$ {float(x):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
        
        itens_sem_faturamento_180 = itens_sem_faturamento_180[['Empresa', 'Grupo Interno', 'cod_item', 'quantidade_estoque', 'Custo Contabil']]
        itens_sem_faturamento_180['Custo Contabil'] = itens_sem_faturamento_180['Custo Contabil'].apply(lambda x: f"R$ {float(x):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))

        itens_sem_faturamento_360 = itens_sem_faturamento_360[['Empresa', 'Grupo Interno', 'cod_item', 'quantidade_estoque', 'Custo Contabil']]
        itens_sem_faturamento_360['Custo Contabil'] = itens_sem_faturamento_360['Custo Contabil'].apply(lambda x: f"R$ {float(x):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))

        # Exibindo os dados filtrados
        
        st.write(f"**Data de atualização: {datetime.now()}**")
        st.subheader("Itens sem faturamento nos últimos 90 dias")
        st.write(f"**Valor total do estoque: R$ {valor_total_estoque_90:,.2f}**")
        
        st.dataframe(df_filtrado_90[['Empresa','Grupo Interno','cod_item','quantidade_estoque','Custo Contabil']], hide_index=True)
        
        # Adicionado DF 180 dias
        st.subheader("Itens sem faturamento nos últimos 180 dias")
        st.write(f"**Valor total do estoque: R$ {valor_total_estoque_180:,.2f}**")
        
        st.dataframe(df_filtrado_180[['Empresa','Grupo Interno','cod_item','quantidade_estoque','Custo Contabil']], hide_index=True)
        
        # Adicionando DF 360 dias
        st.subheader("Itens sem faturamento nos últimos 365 dias")
        st.write(f"**Valor total do estoque: R$ {valor_total_estoque_360:,.2f}**")
        st.dataframe(df_filtrado_360[['Empresa','Grupo Interno','cod_item','quantidade_estoque','Custo Contabil']], hide_index=True)

    if menu == "CRM":
        st.title("Acompanhamento de CRM")
        data_inicial = st.sidebar.date_input("Data Inicial", datetime.now())
        data_final = st.sidebar.date_input("Data Final", datetime.now())
        query = f"""
                    SELECT
                    ce.COD_EVENTO ,
                    cet.COD_GRUPO,
                    cg.desc_grupo,
                    ce.cod_tipo_evento,
                    ce.status,
                    oa.cod_os_agenda,
                    CASE
                        WHEN pm.DESCRICAO_MODELO IS NOT NULL THEN pm.DESCRICAO_MODELO
                        ELSE pm2.descricao_modelo
                    END modelo_veiculo, 
                    cet.desc_tipo_evento,
                    eu3.nome_completo agendador,
                    ce.cod_empresa,
                    oa.numero_os,
                    o.status_os,
                    cmp.desc_motivo motivo_perda,
                    cd.descricao_descarte,
                    (
                    SELECT
                        LISTAGG(srv.DESCRICAO_SERVICO, ', ') WITHIN GROUP (
                        ORDER BY srv.DESCRICAO_SERVICO)
                    FROM
                        OS_SERVICOS oss
                    LEFT JOIN servicos srv ON
                        srv.cod_servico = oss.cod_servico
                    WHERE
                        oss.NUMERO_OS = o.NUMERO_OS
                        AND oss.COD_EMPRESA = o.COD_EMPRESA) servicos,
                    (SELECT LISTAGG(oar.descricao, ', ') WITHIN GROUP (ORDER BY oar.descricao)
                            FROM OS_AGENDA_RECLAMACAO oar
                                WHERE 1=1
                                    AND oa.COD_OS_AGENDA  = oar.COD_OS_AGENDA 
                                    AND oa.COD_EMPRESA = oar.COD_EMPRESA) reclamacoes
                FROM
                    crm_eventos ce
                LEFT JOIN CRM_EVENTOS_TIPO cet ON
                    1 = 1
                    AND cet.COD_TIPO_EVENTO = ce.COD_TIPO_EVENTO
                left join CRM_DESCARTES cd on 1=1
                    and cd.COD_DESCARTE = ce.COD_DESCARTE
                LEFT JOIN CRM_MOTIVO_PERDAS cmp ON 1=1
                    AND cmp.cod_motivo_perda = ce.cod_motivo_perda
                LEFT JOIN CRM_GRUPO cg ON
                    1 = 1
                    AND cg.COD_GRUPO = cet.COD_GRUPO
                LEFT JOIN OS_AGENDA oa ON
                    1 = 1
                    AND oa.cod_empresa = ce.COD_EMPRESA
                    AND oa.CRM_COD_EVENTO = ce.COD_EVENTO
                LEFT JOIN CLIENTES c ON 1=1
                    AND c.COD_CLIENTE = oa.cod_cliente
                LEFT JOIN PRISMA_BOX pb ON 1=1
                    AND pb.PRISMA = oa.PRISMA 
                LEFT JOIN produtos p ON 1=1
                    AND p.COD_PRODUTO = oa.COD_PRODUTO 
                LEFT JOIN PRODUTOS_MODELOS pm ON 1=1
                    AND pm.COD_PRODUTO = oa.COD_PRODUTO 
                    AND pm.COD_MODELO = oa.COD_MODELO
                LEFT JOIN PRODUTOS_MODELOS pm2 ON 1=1
                    AND pm2.COD_PRODUTO = ce.veic_COD_PRODUTO 
                    AND pm2.COD_MODELO = ce.veic_COD_MODELO
                LEFT JOIN EMPRESAS_USUARIOS eu ON 1=1
                    AND eu.nome = ce.RESPONSAVEL_PELO_EVENTO
                LEFT JOIN os o ON
                    1 = 1
                    AND o.NUMERO_OS = oa.NUMERO_OS
                    AND o.COD_EMPRESA = oa.COD_EMPRESA
                LEFT JOIN empresas_usuarios eu3 ON 1=1
                    AND eu3.NOME = oa.quem_abriu
                WHERE
                    1 = 1
                    AND ce.COD_EMPRESA IN (11, 33)
                    AND ce.data_evento >= TO_DATE('{data_inicial}', 'YYYY-MM-DD')
                    AND ce.data_evento <= TO_DATE('{data_final}', 'YYYY-MM-DD')
                """
        con, cur = oracle()
        cur.execute(query)
        results = cur.fetchall()
        df = pd.DataFrame(results, columns=[desc[0] for desc in cur.description], dtype=str)
        cur.close()
        con.close()
        df = df.replace({None: np.nan, 'None': np.nan})
        df.loc[df['STATUS'].astype(str).str.upper().eq('P'), 'STATUS'] = 'Pendente'
        df.loc[df['STATUS'].astype(str).str.upper().eq('E'), 'STATUS'] = 'Encerrado'
        df.loc[df['STATUS'].astype(str).str.upper().eq('D'), 'STATUS'] = 'Descartado'
        df.loc[df['STATUS'].astype(str).str.upper().eq('V'), 'STATUS'] = 'Visita Agendada'
        df.loc[df['STATUS'].astype(str).str.upper().eq('R'), 'STATUS'] = 'Remarcou'
        df.loc[df['STATUS'].astype(str).str.upper().eq('A'), 'STATUS'] = 'Evento tem ações'
        df = df[df['STATUS'] != 'Pendente']
        df.loc[~df['STATUS'].isin(['Descartado']), 'STATUS'] = 'Encerrado'
        df = df[df['COD_TIPO_EVENTO'] != '267']
        ciclo = df[df['COD_GRUPO'] == '-1'].reset_index(drop=True)
        df = df[df['COD_GRUPO'] != '-1'].reset_index(drop=True)
        df = df[df['COD_GRUPO'] == '3'].reset_index(drop=True)
        encerrados = pd.concat([df, ciclo], ignore_index=True)
        encerrados.loc[(encerrados['STATUS_OS'] != '1.0') & (encerrados['STATUS'] != 'Descartado'), 'STATUS'] = 'Encerrado com erro'
        encerrados.loc[encerrados['MOTIVO_PERDA'].notnull(), 'STATUS'] = 'CONTATO PERDIDO'
        str_cols = encerrados.select_dtypes(include=['object', 'string']).columns
        encerrados[str_cols] = encerrados[str_cols].map(
            lambda x: ''.join(ch for ch in unicodedata.normalize('NFKD', x) if not unicodedata.combining(ch)) if isinstance(x, str) else x
        )
        encerrados[str_cols] = encerrados[str_cols].map(
            lambda x: ' '.join(x.split()) if isinstance(x, str) else x
        )
        encerrados[str_cols] = encerrados[str_cols].map(lambda x: x.upper() if isinstance(x, str) else x)
        num = r'(?:\d{1,3}(?:[.,]\d{3})+|\d+)'
        pat = rf'((?:\bREVISAO\s+DE\s+{num}(?:(?:\s*KMS?)\b)?)|(?:\bREVISAO\s+{num}(?=\s*KMS?\b|\b)))'
        encerrados['NOME_REVISAO'] = encerrados['SERVICOS'].str.extract(pat, expand=False) if not encerrados['SERVICOS'].isnull().all() else np.nan
        encerrados['NOME_REVISAO'] = encerrados['NOME_REVISAO'].str.replace(' DE ', ' ', regex=False) if not encerrados['NOME_REVISAO'].isnull().all() else np.nan
        encerrados['NOME_REVISAO'] = encerrados['NOME_REVISAO'].str.replace('KMS', '', regex=False) if not encerrados['NOME_REVISAO'].isnull().all() else np.nan
        encerrados['NOME_REVISAO'] = encerrados['NOME_REVISAO'].str.replace('KM', '', regex=False) if not encerrados['NOME_REVISAO'].isnull().all() else np.nan
        encerrados['NOME_REVISAO'] = encerrados['NOME_REVISAO'].str.strip() if not encerrados['NOME_REVISAO'].isnull().all() else np.nan
        encerrados['TIPO_ATENDIMENTO'] = encerrados['DESC_TIPO_EVENTO'].str.split(' - ').str[-1]
        
        
        eventos_descartados = encerrados[encerrados['STATUS'] == 'DESCARTADO'].reset_index(drop=True)
        eventos_descartados_motivos = pd.pivot_table(
        eventos_descartados,
        index=['DESCRICAO_DESCARTE'],
        values=['COD_EVENTO'],
        aggfunc={'COD_EVENTO': 'count'}
        ).reset_index().rename(columns={'COD_EVENTO': 'TOTAL_EVENTOS'})
        # adicione o dataframe na metade esquerda da tela e um grafico na metade direita
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Eventos descartados por motivo")
            st.dataframe(eventos_descartados_motivos, hide_index=True)
        with col2:
            st.subheader("Gráfico de eventos descartados por motivo")
            fig = px.bar(eventos_descartados_motivos, x='DESCRICAO_DESCARTE', y='TOTAL_EVENTOS', text='TOTAL_EVENTOS')
            fig.update_traces(textposition='outside')
            fig.update_layout(yaxis_title='Total de Eventos', xaxis_title='Motivo de Descarte', uniformtext_minsize=8, uniformtext_mode='hide')
            st.plotly_chart(fig, use_container_width=True)
        
        
        filtro = (encerrados['STATUS'] != 'DESCARTADO') & (encerrados['STATUS_OS'].astype(str) == '1.0')
        eventos_encerrados_por_revisao = (
            pd.pivot_table(
                encerrados.loc[filtro],
                index='NOME_REVISAO',
                columns='TIPO_ATENDIMENTO',
                values='COD_EVENTO',
                aggfunc='count'
            )
            .fillna(0)
            .rename_axis(index=None, columns=None)
            .reset_index()
        )
        # rename first column to NOME_REVISAO
        eventos_encerrados_por_revisao = eventos_encerrados_por_revisao.rename(columns={'index': 'NOME REVISAO'})
        
        # total ativos x PASSANTES
        total_ativos = eventos_encerrados_por_revisao['ATIVO'].sum() if 'ATIVO' in eventos_encerrados_por_revisao.columns else 0
        total_passantes = eventos_encerrados_por_revisao['PASSANTE'].sum() if 'PASSANTE' in eventos_encerrados_por_revisao.columns else 0
        total_receptivos = eventos_encerrados_por_revisao['RECEPTIVO'].sum() if 'RECEPTIVO' in eventos_encerrados_por_revisao.columns else 0
        col3, col4 = st.columns(2)
        with col3:
            st.subheader("Eventos encerrados com SUCESSO ! por revisão")
            st.dataframe(eventos_encerrados_por_revisao, hide_index=True)
        with col4:
            st.subheader("Gráfico de Ativos vs. Passantes")
            
            # Cria um DataFrame para o gráfico de pizza
            df_pie = pd.DataFrame({
                'Tipo': ['Ativos', 'Passantes'],
                'Total': [total_ativos, total_passantes]
            })
            
            # Cria o gráfico de pizza
            fig2 = px.pie(df_pie, values='Total', names='Tipo', title='Comparativo Ativos vs. Passantes')
            fig2.update_traces(textposition='inside', textinfo='percent+label+value')
            st.plotly_chart(fig2, use_container_width=True)
        
        # exibir planilha grande de detalhamento para download
        st.subheader("Detalhamento dos eventos encerrados")
        planilha = io.BytesIO()
        with pd.ExcelWriter(planilha, engine='xlsxwriter') as writer:
            encerrados.to_excel(writer, index=False, sheet_name='Eventos Encerrados')
            eventos_descartados.to_excel(writer, index=False, sheet_name='Eventos Descartados')
            eventos_descartados_motivos.to_excel(writer, index=False, sheet_name='Descartes por Motivo')
            eventos_encerrados_por_revisao.to_excel(writer, index=False, sheet_name='Encerrados por Revisao')
            writer.close()
            planilha.seek(0)
            st.download_button(
                label="Download da planilha completa",
                data=planilha.getvalue(),
                file_name="acompanhamento_crm.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        
        col5, col6 = st.columns(2)
        eventos_encerrados_com_sucesso_por_tipo = (
            pd.pivot_table(
                encerrados.loc[filtro],
                index='DESC_TIPO_EVENTO',
                values='COD_EVENTO',
                aggfunc='count'
            )
            .fillna(0)
            .rename_axis(index=None)
            .reset_index()
            .rename(columns={'COD_EVENTO': 'TOTAL_EVENTOS'})
        )
        eventos_encerrados_com_sucesso_por_tipo.rename(columns={'index': 'TIPO ATENDIMENTO'}, inplace=True)
        # se total de eventos for maior que 0, exibir

        if not eventos_encerrados_com_sucesso_por_tipo.empty and eventos_encerrados_com_sucesso_por_tipo['TOTAL_EVENTOS'].sum() > 0:
            with col5:
                st.subheader("Eventos encerrados com SUCESSO ! por tipo de atendimento")
                st.dataframe(eventos_encerrados_com_sucesso_por_tipo, hide_index=True)
            with col6:
                st.subheader("Gráfico de eventos encerrados com SUCESSO ! por tipo de atendimento")
                fig3 = px.bar(eventos_encerrados_com_sucesso_por_tipo, x='TIPO ATENDIMENTO', y='TOTAL_EVENTOS', text='TOTAL_EVENTOS', title="Total de Eventos por Tipo de Atendimento")
                fig3.update_traces(textposition='outside')
                fig3.update_layout(yaxis_title='Total de Eventos', xaxis_title='Tipo de Atendimento', uniformtext_minsize=8, uniformtext_mode='hide', xaxis_tickangle=-45)
                st.plotly_chart(fig3, use_container_width=True)

    if menu == "Fluxo de loja":
        st.title("Acompanhamento de Fluxo de Loja")
        # st.write("Em desenvolvimento...")
        data_inicial = st.sidebar.date_input("Data Inicial", datetime.now())
        data_final = st.sidebar.date_input("Data Final", datetime.now())
        query = f"""
            SELECT 
                eu.cod_empresa,
                concat(ce.COD_EMPRESA, ce.COD_EVENTO) cod_evento,
                CASE
                    WHEN ca.andamento IS NULL THEN 'Não informado'
                    ELSE ca.andamento
                END andamento,
                CASE
                    WHEN ce.status = 'P' THEN 'Pendente'
                    WHEN ce.status = 'E' THEN 'Encerrado'
                    WHEN ce.status = 'D' THEN 'Descartado'
                    WHEN ce.status = 'V' THEN 'Pendente'
                    WHEN ce.status = 'R' THEN 'Pendente'
                    WHEN ce.status = 'A' THEN 'Pendente'
                    ELSE 'Não informado'
                END status,
                CASE
                    WHEN TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) < TRUNC(SYSDATE) THEN 'ATRASADO'
                    WHEN TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) = TRUNC(SYSDATE) THEN 'HOJE'
                    WHEN TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) > TRUNC(SYSDATE) THEN 'FUTURO'
                END AS status_atendimento,
                CASE
                    WHEN ce.COD_CLIENTE = 1 THEN ce.NOME_CLIENTE_AVULSO 
                    ELSE c.NOME 
                END nome_cliente,
                TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) data_contato,
                --ce.data_agendada,
                --ce.data_visita,
                ce.cod_proposta,
                upper(cet.DESC_TIPO_EVENTO) tipo_evento,
                CASE
                    WHEN eu.NOME_COMPLETO IS NOT NULL THEN upper(eu.NOME_COMPLETO)
                    ELSE 
                        'SEM RESPONSÁVEL'
                END responsavel,
                CASE 
                    WHEN ce.cod_modelo IS NOT NULL THEN pm.descricao_modelo
                    ELSE
                        'VEÍCULO NAO DEFINIDO'
                END VEICULO,
                (SELECT count(*) FROM CAIUAS_CRM_RETORNO ccr
                WHERE 1=1
                    AND ccr.COD_EMPRESA = ce.COD_EMPRESA 
                    AND ccr.COD_EVENTO = ce.COD_EVENTO 
                ) qtd_retornos,
                CASE
                    WHEN (SELECT count(*) FROM caiuas_crm_test_drive cctd WHERE cctd.COD_EMPRESA = ce.COD_EMPRESA AND cctd.COD_EVENTO = ce.COD_EVENTO ) > 0 THEN 'TEM'
                    ELSE 'NÃO'
                END TEM_TEST_DRIVE,
                ce.data_criacao,
                ce.COD_TIPO_EVENTO,
                TRUNC(cel.data_criacao) data_lead,
                CASE
                    WHEN eu_lead.NOME_COMPLETO IS NOT NULL THEN upper(eu_lead.NOME_COMPLETO)
                    ELSE 'SEM RESPONSÁVEL'
                END responsavel_lead,
                TRUNC(cel.data_agendada) data_agendada_lead,
                vp.STATUS_PROPOSTA,
                TRIM(TO_CHAR(ce.COD_EMPRESA_ANTERIOR)) || TRIM(TO_CHAR(ce.COD_EVENTO_ANTERIOR)) cod_evento_anterior
                FROM crm_eventos ce
                LEFT JOIN CRM_ANDAMENTO ca ON 1=1
                    AND ca.COD_ANDAMENTO = ce.COD_ANDAMENTO 
                LEFT JOIN CRM_EVENTOS_TIPO cet ON 1=1
                    AND cet.COD_TIPO_EVENTO = ce.COD_TIPO_EVENTO 
                LEFT JOIN EMPRESAS_USUARIOS eu ON 1=1
                    AND eu.NOME = ce.RESPONSAVEL_PELO_EVENTO 
                LEFT JOIN PRODUTOS_MODELOS pm ON 1=1
                    AND pm.COD_MODELO = ce.COD_MODELO 
                LEFT JOIN MIDIA m ON m.COD_MIDIA = ce.COD_MIDIA 
                LEFT JOIN clientes c ON ce.COD_CLIENTE = c.COD_CLIENTE
                LEFT JOIN crm_eventos cel ON 1=1
                    AND ce.COD_EVENTO_ANTERIOR = cel.COD_EVENTO
                    AND ce.COD_EMPRESA_ANTERIOR = cel.COD_EMPRESA
                LEFT JOIN EMPRESAS_USUARIOS eu_lead ON 1=1
                    AND eu_lead.NOME = cel.RESPONSAVEL_PELO_EVENTO
                LEFT JOIN VEICULOS_PROPOSTAS vp ON 1=1
                	AND vp.COD_PROPOSTA = ce.COD_PROPOSTA
                WHERE 1=1
                    AND ce.COD_TIPO_EVENTO IN (785,807)
                    AND ce.status <> 'D'
                    AND TRUNC(ce.DATA_CRIACAO) >= TO_DATE('{data_inicial}', 'YYYY-MM-DD') AND TRUNC(ce.DATA_CRIACAO) <= TO_DATE('{data_final}', 'YYYY-MM-DD')
        """
        con, cur = oracle()
        cur.execute(query)
        results = cur.fetchall()
        df = pd.DataFrame(results, columns=[desc[0] for desc in cur.description], dtype=str)
        query = f"""
            SELECT 
            eu.cod_empresa,
            concat(ce.COD_EMPRESA, ce.COD_EVENTO) cod_evento,
            CASE
                WHEN ca.andamento IS NULL THEN 'Não informado'
                ELSE ca.andamento
            END andamento,
            CASE
                WHEN ce.status = 'P' THEN 'Pendente'
                WHEN ce.status = 'E' THEN 'Encerrado'
                WHEN ce.status = 'D' THEN 'Descartado'
                WHEN ce.status = 'V' THEN 'Pendente'
                WHEN ce.status = 'R' THEN 'Pendente'
                WHEN ce.status = 'A' THEN 'Pendente'
                ELSE 'Não informado'
            END status,
            CASE
                WHEN TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) < TRUNC(SYSDATE) THEN 'ATRASADO'
                WHEN TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) = TRUNC(SYSDATE) THEN 'HOJE'
                WHEN TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) > TRUNC(SYSDATE) THEN 'FUTURO'
            END AS status_atendimento,
            CASE
                WHEN ce.COD_CLIENTE = 1 THEN ce.NOME_CLIENTE_AVULSO 
                ELSE c.NOME 
            END nome_cliente,
            TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) data_contato,
            --ce.data_agendada,
            --ce.data_visita,
            ce.cod_proposta,
            upper(cet.DESC_TIPO_EVENTO) tipo_evento,
            CASE
                WHEN eu.NOME_COMPLETO IS NOT NULL THEN upper(eu.NOME_COMPLETO)
                ELSE 
                    'SEM RESPONSÁVEL'
            END responsavel,
            CASE 
                WHEN ce.cod_modelo IS NOT NULL THEN pm.descricao_modelo
                ELSE
                    'VEÍCULO NAO DEFINIDO'
            END VEICULO,
            (SELECT count(*) FROM CAIUAS_CRM_RETORNO ccr
            WHERE 1=1
                AND ccr.COD_EMPRESA = ce.COD_EMPRESA 
                AND ccr.COD_EVENTO = ce.COD_EVENTO 
            ) qtd_retornos,
            CASE
                WHEN (SELECT count(*) FROM caiuas_crm_test_drive cctd WHERE cctd.COD_EMPRESA = ce.COD_EMPRESA AND cctd.COD_EVENTO = ce.COD_EVENTO ) > 0 THEN 'TEM'
                ELSE 'NÃO'
            END TEM_TEST_DRIVE,
            ce.data_criacao,
            ce.COD_TIPO_EVENTO,
            TRUNC(cel.data_criacao) data_lead,
            CASE
                WHEN eu_lead.NOME_COMPLETO IS NOT NULL THEN upper(eu_lead.NOME_COMPLETO)
                ELSE 'SEM RESPONSÁVEL'
            END responsavel_lead,
            TRUNC(cel.data_agendada) data_agendada_lead,
            vp.STATUS_PROPOSTA,
            TRIM(TO_CHAR(ce.COD_EMPRESA_ANTERIOR)) || TRIM(TO_CHAR(ce.COD_EVENTO_ANTERIOR)) cod_evento_anterior
            FROM crm_eventos ce
            LEFT JOIN CRM_ANDAMENTO ca ON 1=1
                AND ca.COD_ANDAMENTO = ce.COD_ANDAMENTO 
            LEFT JOIN CRM_EVENTOS_TIPO cet ON 1=1
                AND cet.COD_TIPO_EVENTO = ce.COD_TIPO_EVENTO 
            LEFT JOIN EMPRESAS_USUARIOS eu ON 1=1
                AND eu.NOME = ce.RESPONSAVEL_PELO_EVENTO 
            LEFT JOIN PRODUTOS_MODELOS pm ON 1=1
                AND pm.COD_MODELO = ce.COD_MODELO 
            LEFT JOIN MIDIA m ON m.COD_MIDIA = ce.COD_MIDIA 
            LEFT JOIN clientes c ON ce.COD_CLIENTE = c.COD_CLIENTE
            LEFT JOIN crm_eventos cel ON 1=1
                AND ce.COD_EVENTO_ANTERIOR = cel.COD_EVENTO
                AND ce.COD_EMPRESA_ANTERIOR = cel.COD_EMPRESA
            LEFT JOIN EMPRESAS_USUARIOS eu_lead ON 1=1
                AND eu_lead.NOME = cel.RESPONSAVEL_PELO_EVENTO
            LEFT JOIN VEICULOS_PROPOSTAS vp ON 1=1
                AND vp.COD_PROPOSTA = ce.COD_PROPOSTA
            WHERE 1=1
                AND ce.COD_TIPO_EVENTO IN (819,821,815,817,810,812)
                AND ce.status <> 'D'
                AND TRUNC(ce.DATA_VISITA) >= TO_DATE('{data_inicial}', 'YYYY-MM-DD') AND TRUNC(ce.DATA_VISITA) <= TO_DATE('{data_final}', 'YYYY-MM-DD')
        """
        cur.execute(query)
        results = cur.fetchall()
        df_visitas = pd.DataFrame(results, columns=[desc[0] for desc in cur.description], dtype=str)
        # concatena df e df_visitas
        df = pd.concat([df, df_visitas], ignore_index=True)
        
        
        # remova o .0 do cod_proposta ele é SRT
        df['COD_PROPOSTA'] = df['COD_PROPOSTA'].str.replace('.0', '', regex=False)
        
        # se status_proposta = 'V' altere o status do evento para "Faturado", se tiver proposta e se status da proposta for "C" altere o status do evento para proposta cancelada, se for outro adicione Aguardando cancelamento
        df['STATUS'] = df.apply(lambda row: 'Faturado' if row['STATUS_PROPOSTA'] == 'V' else ('Proposta Cancelada' if row['STATUS_PROPOSTA'] == 'C' else ('Aguardando faturamento' if row['STATUS_PROPOSTA'] not in ['V', 'C', None, ''] else row['STATUS'])), axis=1)
        df['STATUS_ATENDIMENTO'] = df.apply(lambda row: 'Faturado' if row['STATUS_PROPOSTA'] == 'V' else ('Proposta Cancelada' if row['STATUS_PROPOSTA'] == 'C' else ('Aguardando faturamento' if row['STATUS_PROPOSTA'] not in ['V', 'C', None, ''] else row['STATUS'])), axis=1)
        
        
        
        query = f"""
        SELECT
            ccr.cod_empresa,
            concat(ce.COD_EMPRESA, ce.COD_EVENTO) cod_evento,
            TRUNC(ccr.created_at) data_retorno,
            CASE
                WHEN ca.andamento IS NULL THEN 'Não informado'
                ELSE ca.andamento
            END andamento,
            CASE
                WHEN ce.status = 'P' THEN 'Pendente'
                WHEN ce.status = 'E' THEN 'Encerrado'
                WHEN ce.status = 'D' THEN 'Descartado'
                WHEN ce.status = 'V' THEN 'Pendente'
                WHEN ce.status = 'R' THEN 'Pendente'
                WHEN ce.status = 'A' THEN 'Pendente'
                ELSE 'Não informado'
            END status,
            CASE
                WHEN ce.COD_CLIENTE = 1 THEN ce.NOME_CLIENTE_AVULSO
                ELSE c.NOME
            END nome_cliente,
            ce.cod_proposta,
            upper(cet.DESC_TIPO_EVENTO) tipo_evento,
            CASE
                WHEN eu.NOME_COMPLETO IS NOT NULL THEN upper(eu.NOME_COMPLETO)
                ELSE 'SEM RESPONSÁVEL'
            END responsavel,
            CASE
                WHEN ce.cod_modelo IS NOT NULL THEN pm.descricao_modelo
                ELSE 'VEÍCULO NAO DEFINIDO'
            END veiculo,
            (SELECT count(*) FROM CAIUAS_CRM_RETORNO ccr2
             WHERE ccr2.COD_EMPRESA = ce.COD_EMPRESA
               AND ccr2.COD_EVENTO = ce.COD_EVENTO) qtd_retornos,
            CASE
                WHEN (SELECT count(*) FROM caiuas_crm_test_drive cctd WHERE cctd.COD_EMPRESA = ce.COD_EMPRESA AND cctd.COD_EVENTO = ce.COD_EVENTO) > 0 THEN 'TEM'
                ELSE 'NÃO'
            END tem_test_drive,
            TRUNC(ce.data_criacao) data_criacao
        FROM CAIUAS_CRM_RETORNO ccr
        LEFT JOIN crm_eventos ce ON 1=1
            AND ce.COD_EVENTO = ccr.COD_EVENTO
            AND ce.COD_EMPRESA = ccr.COD_EMPRESA
        LEFT JOIN CRM_ANDAMENTO ca ON 1=1
            AND ca.COD_ANDAMENTO = ce.COD_ANDAMENTO
        LEFT JOIN CRM_EVENTOS_TIPO cet ON 1=1
            AND cet.COD_TIPO_EVENTO = ce.COD_TIPO_EVENTO
        LEFT JOIN EMPRESAS_USUARIOS eu ON 1=1
            AND eu.NOME = ce.RESPONSAVEL_PELO_EVENTO
        LEFT JOIN PRODUTOS_MODELOS pm ON 1=1
            AND pm.COD_MODELO = ce.COD_MODELO
        LEFT JOIN MIDIA m ON 1=1
            AND m.COD_MIDIA = ce.COD_MIDIA
        LEFT JOIN clientes c ON ce.COD_CLIENTE = c.COD_CLIENTE
        LEFT JOIN crm_eventos cel ON 1=1
            AND ce.COD_EVENTO_ANTERIOR = cel.COD_EVENTO 
            AND ce.COD_EMPRESA_ANTERIOR = cel.COD_EMPRESA
        WHERE 1=1
            AND ce.status <> 'D'
            and ce.COD_TIPO_EVENTO IN (819,821,815,817,810,812,829,831,795,793,797,799,787,833,825,785,807,827,823)
            AND TRUNC(ccr.created_at) >= TO_DATE('{data_inicial}', 'YYYY-MM-DD')
            AND TRUNC(ccr.created_at) <= TO_DATE('{data_final}', 'YYYY-MM-DD')
        """
        cur.execute(query)
        results = cur.fetchall()
        df_retorno = pd.DataFrame(results, columns=[desc[0] for desc in cur.description])
        
        cur.close()
        con.close()
        
        # Converter colunas de data para datetime
        df['DATA_CONTATO'] = pd.to_datetime(df['DATA_CONTATO'], errors='coerce')
        
        # Formatar datas como string (YYYY-MM-DD) e substituir NaT por string vazia
        df['DATA_CONTATO'] = df['DATA_CONTATO'].dt.strftime('%Y-%m-%d').fillna('-')
        df['DATA_LEAD'] = pd.to_datetime(df['DATA_LEAD'], errors='coerce')
        df['DATA_LEAD'] = df['DATA_LEAD'].dt.strftime('%Y-%m-%d').fillna('-')
        df['DATA_AGENDADA_LEAD'] = pd.to_datetime(df['DATA_AGENDADA_LEAD'], errors='coerce')
        df['DATA_AGENDADA_LEAD'] = df['DATA_AGENDADA_LEAD'].dt.strftime('%Y-%m-%d').fillna('-')
        
        # Substituir None/NaN nas demais colunas
        df = df.fillna('-')
        df['COD_EVENTO_ANTERIOR'] = df['COD_EVENTO_ANTERIOR'].replace('-', '')
        df['link_fluxo'] = df['COD_EVENTO'].apply(lambda x: f"https://app.caiuas.com.br/crm/eventos/{x}")
        df['link_lead'] = df['COD_EVENTO_ANTERIOR'].apply(
            lambda x: f"https://app.caiuas.com.br/crm/eventos/{x}" if str(x).strip() != '' else ''
        )
        
        df_retorno['DATA_RETORNO'] = pd.to_datetime(df_retorno['DATA_RETORNO'], errors='coerce')
        df_retorno['DATA_RETORNO'] = df_retorno['DATA_RETORNO'].dt.strftime('%Y-%m-%d').fillna('-')
        df_retorno['DATA_CRIACAO'] = pd.to_datetime(df_retorno['DATA_CRIACAO'], errors='coerce')
        df_retorno['DATA_CRIACAO'] = df_retorno['DATA_CRIACAO'].dt.strftime('%Y-%m-%d').fillna('-')
        df_retorno = df_retorno.fillna('-')
        df_retorno['LINK'] = df_retorno['COD_EVENTO'].apply(lambda x: f"https://app.caiuas.com.br/crm/eventos/{x}")
        
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name="Primeira passagem")
            df_retorno.to_excel(writer, index=False, sheet_name="Retornos")
        excel_buffer.seek(0)
        st.download_button(
            label="Download da planilha de eventos",
            data=excel_buffer,
            file_name="eventos_fluxo_de_loja.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        empresa_selecionada = st.sidebar.selectbox("Filtrar por empresa", ["Todas", '11', '33'])
        if empresa_selecionada != "Todas":
            df = df[df['COD_EMPRESA'] == empresa_selecionada]

        responsaveis = df['RESPONSAVEL'].unique()
        responsavel_selecionado = st.sidebar.selectbox("Filtrar por responsável", ["Todos"] + list(responsaveis))
        if responsavel_selecionado != "Todos":
            df = df[df['RESPONSAVEL'] == responsavel_selecionado]
        
        # filtro por status de atendimento
        statuses = df['STATUS_ATENDIMENTO'].unique()
        status_selecionado = st.sidebar.selectbox("Filtrar por status de atendimento", ["Todos"] + list(statuses))
        if status_selecionado != "Todos":
            df = df[df['STATUS_ATENDIMENTO'] == status_selecionado]
        
        test_drives = df['TEM_TEST_DRIVE'].unique()
        test_drive_selecionado = st.sidebar.selectbox("Filtrar por test drive", ["Todos"] + list(test_drives))
        if test_drive_selecionado != "Todos":
            df = df[df['TEM_TEST_DRIVE'] == test_drive_selecionado]
        
        status_eventos = df['STATUS'].unique()
        status_evento_selecionado = st.sidebar.selectbox("Filtrar por status do evento", ["Todos"] + list(status_eventos))
        if status_evento_selecionado != "Todos":
            df = df[df['STATUS'] == status_evento_selecionado]
        
        # Buscar feriados no período para cálculo de média
        con_fer, cur_fer = oracle()
        cur_fer.execute(f"""
            SELECT TRUNC(DATA) AS DATA
            FROM FERIADO
            WHERE TRUNC(DATA) >= TO_DATE('{data_inicial}', 'YYYY-MM-DD')
              AND TRUNC(DATA) <= TO_DATE('{data_final}', 'YYYY-MM-DD')
            GROUP BY TRUNC(DATA)
        """)
        feriados_resultado = cur_fer.fetchall()
        cur_fer.close()
        con_fer.close()
        datas_feriados = set()
        for row in feriados_resultado:
            v = row[0]
            if hasattr(v, 'date'):
                datas_feriados.add(v.date())
            elif v is not None:
                import datetime as _dt
                try:
                    datas_feriados.add(_dt.date.fromisoformat(str(v)[:10]))
                except Exception:
                    pass

        # Calcular dias úteis (Seg-Sáb) no período excluindo feriados
        todas_datas = pd.date_range(data_inicial, data_final, freq='D')
        dias_uteis = [d for d in todas_datas if d.weekday() < 6 and d.date() not in datas_feriados]
        num_dias_uteis = len(dias_uteis)

        # Gráfico: Total de Primeiras Passagens vs Retornos
        total_primeiras = len(df)
        total_retornos = len(df_retorno)
        media_por_dia = round(total_primeiras / num_dias_uteis, 1) if num_dias_uteis > 0 else 0
        df_comparativo = pd.DataFrame({
            "Tipo": ["Primeiras Passagens", "Retornos"],
            "Total": [total_primeiras, total_retornos]
        })
        col_chart1, col_chart2, col_chart3 = st.columns([1, 2, 2])
        with col_chart1:
            st.markdown(f"""
            <div style="text-align: center;">
                <p style="font-size: 14px; color: gray; margin-bottom: 0;">Primeiras Passagens</p>
                <p style="font-size: 2rem; font-weight: bold; margin: 0 0 16px 0;">{total_primeiras}</p>
                <p style="font-size: 14px; color: gray; margin-bottom: 0;">Retornos</p>
                <p style="font-size: 2rem; font-weight: bold; margin: 0 0 16px 0;">{total_retornos}</p>
                <p style="font-size: 14px; color: gray; margin-bottom: 0;">Média/dia <span style="font-size: 12px;">(Seg-Sáb s/ feriados)</span></p>
                <p style="font-size: 2rem; font-weight: bold; margin: 0;">{media_por_dia}</p>
                <p style="font-size: 12px; color: gray; margin-top: 2px;">{num_dias_uteis} dias úteis no período</p>
            </div>
            """, unsafe_allow_html=True)
        with col_chart2:
            fig_comparativo = px.bar(
                df_comparativo,
                x="Tipo",
                y="Total",
                text="Total",
                color="Tipo",
                color_discrete_map={"Primeiras Passagens": "#3498db", "Retornos": "#e67e22"},
                title="Primeiras Passagens vs Retornos no período"
            )
            fig_comparativo.update_traces(textposition='outside')
            fig_comparativo.update_layout(showlegend=False, yaxis_title="Total", xaxis_title="")
            st.plotly_chart(fig_comparativo, use_container_width=True)
        with col_chart3:
            st.markdown("**Eventos por Status de Atendimento**")
            df_status_atendimento = (
                df.groupby('STATUS_ATENDIMENTO')['COD_EVENTO']
                .count()
                .reset_index()
                .rename(columns={'STATUS_ATENDIMENTO': 'Status', 'COD_EVENTO': 'Quantidade'})
                .sort_values('Quantidade', ascending=False)
            )
            st.dataframe(df_status_atendimento, hide_index=True, use_container_width=True)

        # Seção com 3 colunas de indicadores
        st.subheader("Indicadores")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Gráfico de pizza - Test Drive
            test_drive_counts = df['TEM_TEST_DRIVE'].value_counts().reset_index()
            test_drive_counts.columns = ['Test Drive', 'Quantidade']
            test_drive_counts['Test Drive'] = test_drive_counts['Test Drive'].replace({'TEM': 'Sim', 'NÃO': 'Não'})
            
            fig_test_drive = px.pie(
                test_drive_counts, 
                values='Quantidade', 
                names='Test Drive', 
                title='Eventos com Test Drive',
                color='Test Drive',
                color_discrete_map={'Sim': '#2ecc71', 'Não': '#e74c3c'}
            )
            fig_test_drive.update_traces(textposition='inside', textinfo='percent+label+value')
            st.plotly_chart(fig_test_drive, use_container_width=True)
        
        with col2:
            eventos_por_responsavel = df.groupby('RESPONSAVEL')['COD_EVENTO'].count().reset_index()
            eventos_por_responsavel.columns = ['Responsável', 'Quantidade']
            eventos_por_responsavel = eventos_por_responsavel.sort_values('Quantidade', ascending=True)
            
            fig_responsavel = px.bar(
                eventos_por_responsavel,
                x='Quantidade',
                y='Responsável',
                orientation='h',
                title='Eventos por Responsável',
                color='Quantidade',
                color_continuous_scale='Blues'
            )
            fig_responsavel.update_layout(
                showlegend=False,
                coloraxis_showscale=False,
                yaxis={'categoryorder': 'total ascending'},
                height=400
            )
            st.plotly_chart(fig_responsavel, use_container_width=True)
        
        with col3:
            # Gráfico de barras - Eventos por Veículo
            eventos_por_veiculo = df.groupby('VEICULO')['COD_EVENTO'].count().reset_index()
            eventos_por_veiculo.columns = ['Veículo', 'Quantidade']
            eventos_por_veiculo = eventos_por_veiculo.sort_values('Quantidade', ascending=True)
            
            fig_veiculo = px.bar(
                eventos_por_veiculo,
                x='Quantidade',
                y='Veículo',
                orientation='h',
                title='Eventos por Veículo',
                color='Quantidade',
                color_continuous_scale='Greens'
            )
            fig_veiculo.update_layout(
                showlegend=False,
                coloraxis_showscale=False,
                yaxis={'categoryorder': 'total ascending'},
                height=400
            )
            st.plotly_chart(fig_veiculo, use_container_width=True)
        # divisor para mais tre colunas
        # st.markdown("---")
        # col4, col5, col6 = st.columns(3)
        # with col4:
        #     # nada
        #     st.empty()
        # with col5:
        #     st.empty()
        # with col6:
        #     st.empty()
            
        
        
        # Tabela: Primeiras passagens por modelo de veículo
        st.subheader("Primeiras passagens por modelo de veículo")
        eventos_por_modelo = (
            df.groupby('VEICULO')['COD_EVENTO']
            .count()
            .reset_index()
            .rename(columns={'VEICULO': 'Modelo', 'COD_EVENTO': 'Quantidade'})
            .sort_values('Quantidade', ascending=False)
        )
        st.dataframe(eventos_por_modelo, hide_index=True)

        # Tabela: Passagens Varejo - CRIS (apenas tipo 785)
        st.subheader("Passagens Varejo - CRIS")
        df_varejo_cris = df[df['COD_TIPO_EVENTO'].isin(['785','815','810'])]
        varejo_cris_por_modelo = (
            df_varejo_cris.groupby('VEICULO')['COD_EVENTO']
            .count()
            .reset_index()
            .rename(columns={'VEICULO': 'Modelo', 'COD_EVENTO': 'Quantidade'})
            .sort_values('Quantidade', ascending=False)
        )
        st.dataframe(varejo_cris_por_modelo, hide_index=True)

        st.subheader("Eventos")
        st.dataframe(
            df, 
            hide_index=True,
            column_config={
                "link_fluxo": st.column_config.LinkColumn(
                    "Link Fluxo",
                    display_text="Abrir"
                ),
                "link_lead": st.column_config.LinkColumn(
                    "Link Lead",
                    display_text="Abrir"
                ),
            }
        )

        st.subheader("Retornos")
        st.dataframe(
            df_retorno,
            hide_index=True,
            column_config={
                "LINK": st.column_config.LinkColumn(
                    "Abrir Evento",
                    display_text="Abrir"
                )
            }
        )

        st.subheader("Propostas Faturadas")
        query_faturadas = f"""
        SELECT 
            vp.VENDEDOR, 
            vp.cod_proposta, 
            vp.STATUS_PROPOSTA, 
            vp.COD_CLIENTE, 
            c.NOME, 
            c.TELEFONE_CEL, 
            c.TELEFONE_COM, 
            c.TELEFONE_RES, 
            c.TELEFONE_FAX, 
            ce.FONE_CLIENTE_AVULSO,
            --CASE
            --    WHEN ce.COD_EVENTO IS NOT NULL THEN concat('https://app.caiuas.com.br/crm/eventos/',concat(ce.COD_EMPRESA, ce.COD_EVENTO))
            --    ELSE null
            --END link_fluxo,
            CASE
                WHEN ce.COD_EVENTO_ANTERIOR IS NOT NULL THEN concat('https://app.caiuas.com.br/crm/eventos/',concat(ce.COD_EMPRESA_ANTERIOR, ce.COD_EVENTO_ANTERIOR))
                ELSE null
            END link_lead
        FROM VEICULOS_PROPOSTAS vp 
        LEFT JOIN clientes c ON 1=1
            AND c.COD_CLIENTE = vp.COD_CLIENTE 
        LEFT JOIN CRM_EVENTOS ce ON 1=1
            AND ce.COD_PROPOSTA = vp.COD_PROPOSTA 
            AND ce.COD_TIPO_EVENTO IN (785,807,819,821,815,817,810,812)
        --LEFT JOIN CRM_EVENTOS ce2 ON 1=1
        --    AND ce2.COD_PROPOSTA = ce.COD_EVENTO_ANTERIOR 
        --    AND ce2.COD_EMPRESA = ce.COD_EMPRESA_ANTERIOR 
        WHERE 1=1
            AND TRUNC(vp.DATA_VENDA) >= TO_DATE('{data_inicial}', 'YYYY-MM-DD')
            AND TRUNC(vp.DATA_VENDA) <= TO_DATE('{data_final}', 'YYYY-MM-DD')
            AND vp.STATUS_PROPOSTA = 'V'
        ORDER BY vp.VENDEDOR, vp.COD_PROPOSTA
        """
        con_fat, cur_fat = oracle()
        cur_fat.execute(query_faturadas)
        results_fat = cur_fat.fetchall()
        df_faturadas = pd.DataFrame(results_fat, columns=[desc[0] for desc in cur_fat.description])
        cur_fat.close()
        con_fat.close()
        df_faturadas = df_faturadas.fillna('')
        df_faturadas.columns = [c.lower() for c in df_faturadas.columns]

        excel_buffer_fat = io.BytesIO()
        with pd.ExcelWriter(excel_buffer_fat, engine='xlsxwriter') as writer:
            df_faturadas.to_excel(writer, index=False, sheet_name="Propostas Faturadas")
        excel_buffer_fat.seek(0)
        st.download_button(
            label="Download Propostas Faturadas",
            data=excel_buffer_fat,
            file_name="propostas_faturadas.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        st.dataframe(
            df_faturadas,
            hide_index=True,
            use_container_width=True,
            column_config={
                "link_fluxo": st.column_config.LinkColumn("Link Fluxo", display_text="Abrir"),
                "link_lead": st.column_config.LinkColumn("Link Lead", display_text="Abrir"),
            }
        )
    
    if menu == "RECEPCAO":
        st.title("Acompanhamento - Fluxo de loja")
        # st.write("Em desenvolvimento...")
        data_inicial = st.sidebar.date_input("Data Inicial", datetime.now())
        data_final = st.sidebar.date_input("Data Final", datetime.now())
        query = f"""
            SELECT 
                eu.COD_EMPRESA,
                concat(ce.COD_EMPRESA, ce.COD_EVENTO) cod_evento,
                CASE
                    WHEN ca.andamento IS NULL THEN 'Não informado'
                    ELSE ca.andamento
                END andamento,
                CASE
                    WHEN ce.status = 'P' THEN 'Pendente'
                    WHEN ce.status = 'E' THEN 'Encerrado'
                    WHEN ce.status = 'D' THEN 'Descartado'
                    WHEN ce.status = 'V' THEN 'Pendente'
                    WHEN ce.status = 'R' THEN 'Pendente'
                    WHEN ce.status = 'A' THEN 'Pendente'
                    ELSE 'Não informado'
                END status,
                CASE
                    WHEN TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) < TRUNC(SYSDATE) THEN 'ATRASADO'
                    WHEN TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) = TRUNC(SYSDATE) THEN 'HOJE'
                    WHEN TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) > TRUNC(SYSDATE) THEN 'FUTURO'
                END AS status_atendimento,
                CASE
                    WHEN ce.COD_CLIENTE = 1 THEN ce.NOME_CLIENTE_AVULSO 
                    ELSE c.NOME 
                END nome_cliente,
                TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) data_contato,
                ce.data_agendada,
                ce.data_visita,
                upper(cet.DESC_TIPO_EVENTO) tipo_evento,
                CASE
                    WHEN eu.NOME_COMPLETO IS NOT NULL THEN upper(eu.NOME_COMPLETO)
                    ELSE 
                        'SEM RESPONSÁVEL'
                END responsavel,
                CASE 
                    WHEN ce.cod_modelo IS NOT NULL THEN pm.descricao_modelo
                    ELSE
                        'VEÍCULO NAO DEFINIDO'
                END VEICULO,
                (SELECT count(*) FROM CAIUAS_CRM_RETORNO ccr
                WHERE 1=1
                    AND ccr.COD_EMPRESA = ce.COD_EMPRESA 
                    AND ccr.COD_EVENTO = ce.COD_EVENTO 
                ) qtd_retornos,
                CASE
                    WHEN (SELECT count(*) FROM caiuas_crm_test_drive cctd WHERE cctd.COD_EMPRESA = ce.COD_EMPRESA AND cctd.COD_EVENTO = ce.COD_EVENTO ) > 0 THEN 'TEM'
                    ELSE 'NÃO'
                END TEM_TEST_DRIVE,
                ce.data_criacao
                FROM crm_eventos ce
                LEFT JOIN CRM_ANDAMENTO ca ON 1=1
                    AND ca.COD_ANDAMENTO = ce.COD_ANDAMENTO 
                LEFT JOIN CRM_EVENTOS_TIPO cet ON 1=1
                    AND cet.COD_TIPO_EVENTO = ce.COD_TIPO_EVENTO 
                LEFT JOIN EMPRESAS_USUARIOS eu ON 1=1
                    AND eu.NOME = ce.RESPONSAVEL_PELO_EVENTO 
                LEFT JOIN PRODUTOS_MODELOS pm ON 1=1
                    AND pm.COD_MODELO = ce.COD_MODELO 
                LEFT JOIN MIDIA m ON m.COD_MIDIA = ce.COD_MIDIA 
                LEFT JOIN clientes c ON ce.COD_CLIENTE = c.COD_CLIENTE
                WHERE 1=1
                    and ce.status <> 'D'
                    AND ce.COD_TIPO_EVENTO IN (785,807,810,812)
                    AND TRUNC(ce.DATA_CRIACAO) >= TO_DATE('{data_inicial}', 'YYYY-MM-DD') AND TRUNC(ce.DATA_CRIACAO) <= TO_DATE('{data_final}', 'YYYY-MM-DD')
        """
        con, cur = oracle()
        cur.execute(query)
        results = cur.fetchall()
        df = pd.DataFrame(results, columns=[desc[0] for desc in cur.description])
        query = f"""
            SELECT 
                eu.COD_EMPRESA,
                concat(ce.COD_EMPRESA, ce.COD_EVENTO) cod_evento,
                CASE
                    WHEN ca.andamento IS NULL THEN 'Não informado'
                    ELSE ca.andamento
                END andamento,
                CASE
                    WHEN ce.status = 'P' THEN 'Pendente'
                    WHEN ce.status = 'E' THEN 'Encerrado'
                    WHEN ce.status = 'D' THEN 'Descartado'
                    WHEN ce.status = 'V' THEN 'Pendente'
                    WHEN ce.status = 'R' THEN 'Pendente'
                    WHEN ce.status = 'A' THEN 'Pendente'
                    ELSE 'Não informado'
                END status,
                CASE
                    WHEN TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) < TRUNC(SYSDATE) THEN 'ATRASADO'
                    WHEN TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) = TRUNC(SYSDATE) THEN 'HOJE'
                    WHEN TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) > TRUNC(SYSDATE) THEN 'FUTURO'
                END AS status_atendimento,
                CASE
                    WHEN ce.COD_CLIENTE = 1 THEN ce.NOME_CLIENTE_AVULSO 
                    ELSE c.NOME 
                END nome_cliente,
                TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) data_contato,
                ce.data_agendada,
                ce.data_visita,
                upper(cet.DESC_TIPO_EVENTO) tipo_evento,
                CASE
                    WHEN eu.NOME_COMPLETO IS NOT NULL THEN upper(eu.NOME_COMPLETO)
                    ELSE 
                        'SEM RESPONSÁVEL'
                END responsavel,
                CASE 
                    WHEN ce.cod_modelo IS NOT NULL THEN pm.descricao_modelo
                    ELSE
                        'VEÍCULO NAO DEFINIDO'
                END VEICULO,
                (SELECT count(*) FROM CAIUAS_CRM_RETORNO ccr
                WHERE 1=1
                    AND ccr.COD_EMPRESA = ce.COD_EMPRESA 
                    AND ccr.COD_EVENTO = ce.COD_EVENTO 
                ) qtd_retornos,
                CASE
                    WHEN (SELECT count(*) FROM caiuas_crm_test_drive cctd WHERE cctd.COD_EMPRESA = ce.COD_EMPRESA AND cctd.COD_EVENTO = ce.COD_EVENTO ) > 0 THEN 'TEM'
                    ELSE 'NÃO'
                END TEM_TEST_DRIVE,
                ce.data_criacao
                FROM crm_eventos ce
                LEFT JOIN CRM_ANDAMENTO ca ON 1=1
                    AND ca.COD_ANDAMENTO = ce.COD_ANDAMENTO 
                LEFT JOIN CRM_EVENTOS_TIPO cet ON 1=1
                    AND cet.COD_TIPO_EVENTO = ce.COD_TIPO_EVENTO 
                LEFT JOIN EMPRESAS_USUARIOS eu ON 1=1
                    AND eu.NOME = ce.RESPONSAVEL_PELO_EVENTO 
                LEFT JOIN PRODUTOS_MODELOS pm ON 1=1
                    AND pm.COD_MODELO = ce.COD_MODELO 
                LEFT JOIN MIDIA m ON m.COD_MIDIA = ce.COD_MIDIA 
                LEFT JOIN clientes c ON ce.COD_CLIENTE = c.COD_CLIENTE
                WHERE 1=1
                    and ce.status <> 'D'
                    AND ce.COD_TIPO_EVENTO IN (819,821,825,785,807,827,815,817,823,810,812,829,831,795,793,797,799)
                    AND TRUNC(ce.DATA_VISITA) >= TO_DATE('{data_inicial}', 'YYYY-MM-DD') AND TRUNC(ce.DATA_VISITA) <= TO_DATE('{data_final}', 'YYYY-MM-DD')
        """
        cur.execute(query)
        results = cur.fetchall()
        df_retorno = pd.DataFrame(results, columns=[desc[0] for desc in cur.description])
        df = pd.concat([df, df_retorno], ignore_index=True)
        cur.close()
        con.close()
        
        # Converter colunas de data para datetime
        df['DATA_CONTATO'] = pd.to_datetime(df['DATA_CONTATO'], errors='coerce')
        df['DATA_AGENDADA'] = pd.to_datetime(df['DATA_AGENDADA'], errors='coerce')
        df['DATA_VISITA'] = pd.to_datetime(df['DATA_VISITA'], errors='coerce')
        
        # Formatar datas como string (YYYY-MM-DD) e substituir NaT por string vazia
        df['DATA_CONTATO'] = df['DATA_CONTATO'].dt.strftime('%Y-%m-%d').fillna('-')
        df['DATA_AGENDADA'] = df['DATA_AGENDADA'].dt.strftime('%Y-%m-%d').fillna('-')
        df['DATA_VISITA'] = df['DATA_VISITA'].dt.strftime('%Y-%m-%d').fillna('-')
        
        # Substituir None/NaN nas demais colunas
        df = df.fillna('-')
        # link é conct https://app.caiuas.com.br/crm/eventos/ + cod_evento
        df['LINK'] = df['COD_EVENTO'].apply(lambda x: f"https://app.caiuas.com.br/crm/eventos/{x}")
        
        empresa_selecionada = st.sidebar.selectbox("Filtrar por empresa", ["Todas", '11', '33'])
        if empresa_selecionada != "Todas":
            df = df[df['COD_EMPRESA'].astype(str) == empresa_selecionada]
        
        responsaveis = df['RESPONSAVEL'].unique()
        responsavel_selecionado = st.sidebar.selectbox("Filtrar por responsável", ["Todos"] + list(responsaveis))
        if responsavel_selecionado != "Todos":
            df = df[df['RESPONSAVEL'] == responsavel_selecionado]
        
        # filtro por status de atendimento
        statuses = df['STATUS_ATENDIMENTO'].unique()
        status_selecionado = st.sidebar.selectbox("Filtrar por status de atendimento", ["Todos"] + list(statuses))
        if status_selecionado != "Todos":
            df = df[df['STATUS_ATENDIMENTO'] == status_selecionado]
        
        test_drives = df['TEM_TEST_DRIVE'].unique()
        test_drive_selecionado = st.sidebar.selectbox("Filtrar por test drive", ["Todos"] + list(test_drives))
        if test_drive_selecionado != "Todos":
            df = df[df['TEM_TEST_DRIVE'] == test_drive_selecionado]
        
        status_eventos = df['STATUS'].unique()
        status_evento_selecionado = st.sidebar.selectbox("Filtrar por status do evento", ["Todos"] + list(status_eventos))
        if status_evento_selecionado != "Todos":
            df = df[df['STATUS'] == status_evento_selecionado]
        
        tipo_evento = df['TIPO_EVENTO'].unique()
        tipo_evento_selecionado = st.sidebar.selectbox("Filtrar por tipo de evento", ["Todos"] + list(tipo_evento))
        if tipo_evento_selecionado != "Todos":
            df = df[df['TIPO_EVENTO'] == tipo_evento_selecionado]
        
        veiculo = df['VEICULO'].unique()
        veiculo_selecionado = st.sidebar.selectbox("Filtrar por veículo", ["Todos"] + list(veiculo))
        if veiculo_selecionado != "Todos":
            df = df[df['VEICULO'] == veiculo_selecionado]
        
        st.subheader("Detalhes dos eventos")
        busca_cliente = st.text_input("Buscar por nome do cliente", placeholder="Digite parte do nome...")
        if busca_cliente:
            df = df[df['NOME_CLIENTE'].str.contains(busca_cliente.upper(), case=False, na=False)]
        
        st.dataframe(
            df[['NOME_CLIENTE','RESPONSAVEL','TIPO_EVENTO','VEICULO','TEM_TEST_DRIVE','QTD_RETORNOS','DATA_CRIACAO','LINK']], 
            hide_index=True,
            column_config={
                "LINK": st.column_config.LinkColumn(
                    "Abrir Evento",
                    display_text="Abrir"
                )
            }
        )  
        
        # Mover para ANTES do st.dataframe
        df['QTD_ATENDIMENTOS'] = df.groupby('RESPONSAVEL')['RESPONSAVEL'].transform('count')
        df['QTD_EVENTOS'] = df.groupby('TIPO_EVENTO')['TIPO_EVENTO'].transform('count')
        df['QTD_VEICULOS'] = df.groupby('VEICULO')['VEICULO'].transform('count')
        # adicionar uma sessão com duas colunas
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        with col1:
            atendimentos_por_responsavel = df.groupby('RESPONSAVEL')['QTD_ATENDIMENTOS'].max().reset_index()
            atendimentos_por_responsavel.columns = ['Responsável', 'Quantidade']
            fig_atendimentos = px.pie(
                atendimentos_por_responsavel,
                values='Quantidade',
                names='Responsável',
                title='Por Responsável',
                color_discrete_sequence=px.colors.sequential.Blues_r
            )
            fig_atendimentos.update_traces(textinfo='none')
            fig_atendimentos.update_layout(height=350, showlegend=False)
            st.plotly_chart(fig_atendimentos, use_container_width=True)
            st.dataframe(atendimentos_por_responsavel.sort_values('Quantidade', ascending=False), hide_index=True, use_container_width=True)
        with col2:
            eventos_por_tipo = df.groupby('TIPO_EVENTO')['QTD_EVENTOS'].max().reset_index()
            eventos_por_tipo.columns = ['Tipo de Evento', 'Quantidade']
            fig_eventos_tipo = px.pie(
                eventos_por_tipo,
                values='Quantidade',
                names='Tipo de Evento',
                title='Por Tipo de Evento',
                color_discrete_sequence=px.colors.sequential.Greens_r
            )
            fig_eventos_tipo.update_traces(textinfo='none')
            fig_eventos_tipo.update_layout(height=350, showlegend=False)
            st.plotly_chart(fig_eventos_tipo, use_container_width=True)
            st.dataframe(eventos_por_tipo.sort_values('Quantidade', ascending=False), hide_index=True, use_container_width=True)
        with col3:
            eventos_por_veiculo = df.groupby('VEICULO')['QTD_VEICULOS'].max().reset_index()
            eventos_por_veiculo.columns = ['Veículo', 'Quantidade']
            fig_eventos_veiculo = px.pie(
                eventos_por_veiculo,
                values='Quantidade',
                names='Veículo',
                title='Por Veículo',
                color_discrete_sequence=px.colors.sequential.Oranges_r
            )
            fig_eventos_veiculo.update_traces(textinfo='none')
            fig_eventos_veiculo.update_layout(height=350, showlegend=False)
            st.plotly_chart(fig_eventos_veiculo, use_container_width=True)
            st.dataframe(eventos_por_veiculo.sort_values('Quantidade', ascending=False), hide_index=True, use_container_width=True)
         
    if menu == "Veículos":
        st.title("Acompanhamento de veículos")
        # adiciona filtro lateral com seleção de data
        data_inicial = st.sidebar.date_input("Data Inicial", datetime.now())
        data_final = st.sidebar.date_input("Data Final", datetime.now())
        query = f"""
                    SELECT 
                    e.nome,
                    pm.DESCRICAO_MODELO, 
                    p.DESCRICAO_PRODUTO, 
                    v.CHASSI_COMPLETO,
                    v.CHASSI_RESUMIDO,
                    TO_CHAR(v.DATA_VENDA,'YYYY-MM-DD') data_venda ,
                    v.total_nota_fabrica valor_compra,
                    v.DESCONTO_INCONDICIONAL,
                    v.VALOR_VENDIDO,
                    (SELECT sum(valor_final) 
                    FROM veiculos_custos_especificos vce
                    WHERE vce.CHASSI_RESUMIDO = v.CHASSI_RESUMIDO 
                    AND vce.COD_EMPRESA = v.COD_EMPRESA 
                    AND valor_final > 0) custo,
                    v.comissao_vd_bruta
                FROM veiculos v
                LEFT JOIN produtos p ON 1=1
                    AND p.COD_PRODUTO = v.COD_PRODUTO 
                    AND v.COD_MODELO = v.COD_MODELO 
                LEFT JOIN PRODUTOS_MODELOS pm ON 1=1
                    AND pm.COD_MODELO = v.COD_MODELO 
                LEFT JOIN clientes c ON 1=1
                    AND c.COD_CLIENTE = v.COD_CLIENTE 
                LEFT JOIN empresas e ON 1=1
                    AND e.COD_EMPRESA = v.COD_EMPRESA_VENDEDORA
                WHERE 1=1
                    AND trunc(v.DATA_VENDA) >= (TO_DATE('{data_inicial}', 'YYYY-MM-DD'))
                    AND trunc(v.DATA_VENDA) <= (TO_DATE('{data_final}', 'YYYY-MM-DD'))
                    --AND v.CHASSI_COMPLETO = '93HGM6670MZ200149'
                ORDER BY v.CHASSI_COMPLETO 
        """
        conn_oracle, cur_oracle = oracle()
        cur_oracle.execute(query)
        result_oracle = cur_oracle.fetchall()
        cur_oracle.close()
        conn_oracle.close()
        result = pd.DataFrame(result_oracle, columns=[
            "Empresa", "Modelo", "Produto", "Chassi Completo", "Chassi Resumido",
            "Data Venda", "Valor Compra", "Desconto Incondicional", "Valor Vendido", "Custo", "Comissão VD"
        ], dtype=str)
        
        result["Valor Compra"] = result["Valor Compra"].astype(float)
        result["Desconto Incondicional"] = result["Desconto Incondicional"].astype(float)
        result["Valor Vendido"] = result["Valor Vendido"].astype(float)
        
        result["Custo"] = result["Custo"].astype(float)
        result['Comissão VD'] = result['Comissão VD'].astype(float)
        result["Data Venda"] = pd.to_datetime(result["Data Venda"], errors='coerce')
        # replace nan por ''
        result.fillna(0, inplace=True)
        result['lucro'] = result['Valor Vendido'] - result['Custo'] - result['Desconto Incondicional'] - result['Valor Compra'] + result['Comissão VD']
        result['margem'] = result['lucro'] / result['Valor Vendido']
        
        df_agrupado_por_modelo = result.groupby(['Empresa', 'Produto', 'Modelo']).agg({
            'Valor Compra': 'sum',
            'Desconto Incondicional': 'sum',
            'Valor Vendido': 'sum',
            'Custo': 'sum',
            'lucro': 'sum',
            'margem': 'mean'
        }).reset_index()
        
        df_agrupado_por_produto = result.groupby(['Empresa', 'Produto']).agg({
            'Valor Compra': 'sum',
            'Desconto Incondicional': 'sum',
            'Valor Vendido': 'sum',
            'Custo': 'sum',
            'lucro': 'sum',
            'margem': 'mean',
        }).reset_index()
        
        
        
        
        
        # # Filtros na barra lateral
        empresas = result["Empresa"].unique()
        empresa_selecionada = st.sidebar.selectbox("Filtrar por empresa", ["Todas"] + list(empresas))
        modelos = result["Modelo"].unique()
        modelo_selecionado = st.sidebar.selectbox("Filtrar por modelo", ["Todos"] + list(modelos))
        produtos = result["Produto"].unique()
        produto_selecionado = st.sidebar.selectbox("Filtrar por produto", ["Todos"] + list(produtos))
        # quero adicionar um boptão para limpar filtros
        # # Aplicando os filtros
        df_filtrado = result.copy()
        df_filtrado = df_filtrado[['Empresa', 'Modelo', 'Produto', 'Chassi Completo', 'Chassi Resumido', 'Data Venda', 'Valor Compra', 'Desconto Incondicional', 'Valor Vendido','Comissão VD', 'Custo', 'lucro', 'margem']]
        df_agrupado_por_modelo_filtrado = df_agrupado_por_modelo.copy()
        df_agrupado_por_produto_filtrado = df_agrupado_por_produto.copy()

        if empresa_selecionada != "Todas":
            df_filtrado = df_filtrado[df_filtrado["Empresa"] == empresa_selecionada]
            df_agrupado_por_modelo_filtrado = df_agrupado_por_modelo_filtrado[df_agrupado_por_modelo_filtrado["Empresa"] == empresa_selecionada]
            df_agrupado_por_produto_filtrado = df_agrupado_por_produto_filtrado[df_agrupado_por_produto_filtrado["Empresa"] == empresa_selecionada]
        if modelo_selecionado != "Todos":
            df_filtrado = df_filtrado[df_filtrado["Modelo"] == modelo_selecionado]
            df_agrupado_por_modelo_filtrado = df_agrupado_por_modelo_filtrado[df_agrupado_por_modelo_filtrado["Modelo"] == modelo_selecionado]
            df_agrupado_por_produto_filtrado = df_agrupado_por_produto_filtrado[df_agrupado_por_produto_filtrado["Modelo"] == modelo_selecionado]
        if produto_selecionado != "Todos":
            df_filtrado = df_filtrado[df_filtrado["Produto"] == produto_selecionado]
            df_agrupado_por_modelo_filtrado = df_agrupado_por_modelo_filtrado[df_agrupado_por_modelo_filtrado["Produto"] == produto_selecionado]
            df_agrupado_por_produto_filtrado = df_agrupado_por_produto_filtrado[df_agrupado_por_produto_filtrado["Produto"] == produto_selecionado]
        
        # Formatação
        df_agrupado_por_produto_filtrado["Valor Compra"] = df_agrupado_por_produto_filtrado["Valor Compra"].apply(lambda x: f"R$ {float(x):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
        df_agrupado_por_produto_filtrado["Desconto Incondicional"] = df_agrupado_por_produto_filtrado["Desconto Incondicional"].apply(lambda x: f"R$ {float(x):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
        df_agrupado_por_produto_filtrado["Valor Vendido"] = df_agrupado_por_produto_filtrado["Valor Vendido"].apply(lambda x: f"R$ {float(x):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
        df_agrupado_por_produto_filtrado["Custo"] = df_agrupado_por_produto_filtrado["Custo"].apply(lambda x: f"R$ {float(x):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
        df_agrupado_por_produto_filtrado["lucro"] = df_agrupado_por_produto_filtrado["lucro"].apply(lambda x: f"R$ {float(x):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
        df_agrupado_por_produto_filtrado["margem"] = df_agrupado_por_produto_filtrado["margem"].apply(lambda x: f"{float(x):,.2%}".replace(',', 'X').replace('.', ',').replace('X', '.'))   
        
        
        df_agrupado_por_modelo_filtrado["Valor Compra"] = df_agrupado_por_modelo_filtrado["Valor Compra"].apply(lambda x: f"R$ {float(x):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
        df_agrupado_por_modelo_filtrado["Desconto Incondicional"] = df_agrupado_por_modelo_filtrado["Desconto Incondicional"].apply(lambda x: f"R$ {float(x):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
        df_agrupado_por_modelo_filtrado["Valor Vendido"] = df_agrupado_por_modelo_filtrado["Valor Vendido"].apply(lambda x: f"R$ {float(x):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
        df_agrupado_por_modelo_filtrado["Custo"] = df_agrupado_por_modelo_filtrado["Custo"].apply(lambda x: f"R$ {float(x):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
        df_agrupado_por_modelo_filtrado["lucro"] = df_agrupado_por_modelo_filtrado["lucro"].apply(lambda x: f"R$ {float(x):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
        df_agrupado_por_modelo_filtrado["margem"] = df_agrupado_por_modelo_filtrado["margem"].apply(lambda x: f"{float(x):,.2%}".replace(',', 'X').replace('.', ',').replace('X', '.'))
        
        df_filtrado["Valor Compra"] = df_filtrado["Valor Compra"].apply(lambda x: f"R$ {float(x):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
        df_filtrado["Desconto Incondicional"] = df_filtrado["Desconto Incondicional"].apply(lambda x: f"R$ {float(x):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
        df_filtrado["Valor Vendido"] = df_filtrado["Valor Vendido"].apply(lambda x: f"R$ {float(x):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
        df_filtrado["Custo"] = df_filtrado["Custo"].apply(lambda x: f"R$ {float(x):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
        df_filtrado["lucro"] = df_filtrado["lucro"].apply(lambda x: f"R$ {float(x):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
        df_filtrado["margem"] = df_filtrado["margem"].apply(lambda x: f"{float(x):,.2%}".replace(',', 'X').replace('.', ',').replace('X', '.'))
        df_filtrado["Data Venda"] = df_filtrado["Data Venda"].dt.strftime('%d/%m/%Y')
        df_filtrado['Comissão VD'] = df_filtrado['Comissão VD'].apply(lambda x: f"R$ {float(x):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
        excel_buffer = io.BytesIO()
        df_filtrado.to_excel(excel_buffer, index=False, sheet_name="Veículos")
        excel_buffer.seek(0)
        st.download_button(
        label="Exportar para Excel",
        data=excel_buffer,
        file_name="veiculos.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        st.markdown(f"Data de atualização: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        st.markdown("## Veículos vendidos Agrupados por Família")
        st.dataframe(df_agrupado_por_produto_filtrado, hide_index=True)
        st.markdown("## Veículos vendidos Agrupados por Modelo")
        st.dataframe(df_agrupado_por_modelo_filtrado, hide_index=True)
        st.markdown("## Veículos vendidos Detalhado")
        st.dataframe(df_filtrado, hide_index=True)
    
    if menu == "Base Clientes/Veículos":
        st.title("Consulta Base Unificada de Clientes e Veículos")
        
        # Buscar produtos para o filtro
        try:
            conn_pm, cur_pm = oracle()
            cur_pm.execute("""
                SELECT DISTINCT p.COD_PRODUTO, p.DESCRICAO_PRODUTO  
                FROM produtos p
                WHERE p.COD_PRODUTO IN (SELECT DISTINCT COD_PRODUTO FROM produtos_modelos)
                ORDER BY p.DESCRICAO_PRODUTO
            """)
            produtos_result = cur_pm.fetchall()
            produtos_opcoes = {row[1]: row[0] for row in produtos_result}
            cur_pm.close()
            conn_pm.close()
        except Exception as e:
            st.error(f"Erro ao carregar produtos: {e}")
            produtos_opcoes = {}
        
        # Filtros na sidebar
        st.sidebar.subheader("Filtros")
        filtro_chassi = st.sidebar.text_input("Chassi", placeholder="Digite o chassi completo...")
        
        # Multiselect para produtos
        produtos_selecionados = st.sidebar.multiselect(
            "Produtos",
            options=list(produtos_opcoes.keys()),
            placeholder="Selecione os produtos..."
        )
        
        # Buscar modelos baseado nos produtos selecionados (via query SQL)
        modelos_opcoes = {}
        if produtos_selecionados:
            try:
                codigos_produtos = [str(produtos_opcoes[p]) for p in produtos_selecionados]
                conn_mod, cur_mod = oracle()
                cur_mod.execute(f"""
                    SELECT DISTINCT pm.COD_MODELO, pm.DESCRICAO_MODELO  
                    FROM produtos_modelos pm
                    WHERE pm.COD_PRODUTO IN ({','.join(codigos_produtos)})
                    ORDER BY pm.DESCRICAO_MODELO
                """)
                modelos_result = cur_mod.fetchall()
                modelos_opcoes = {row[1]: row[0] for row in modelos_result if row[1]}
                cur_mod.close()
                conn_mod.close()
            except Exception as e:
                st.error(f"Erro ao carregar modelos: {e}")
        else:
            # Se nenhum produto selecionado, carregar todos os modelos
            try:
                conn_mod, cur_mod = oracle()
                cur_mod.execute("""
                    SELECT DISTINCT pm.COD_MODELO, pm.DESCRICAO_MODELO  
                    FROM produtos_modelos pm
                    WHERE pm.DESCRICAO_MODELO IS NOT NULL
                    ORDER BY pm.DESCRICAO_MODELO
                """)
                modelos_result = cur_mod.fetchall()
                modelos_opcoes = {row[1]: row[0] for row in modelos_result if row[1]}
                cur_mod.close()
                conn_mod.close()
            except Exception as e:
                st.error(f"Erro ao carregar modelos: {e}")
        
        # Multiselect para modelos
        modelos_selecionados = st.sidebar.multiselect(
            "Modelos",
            options=list(modelos_opcoes.keys()),
            placeholder="Selecione os modelos..."
        )
        
        # Buscar anos disponíveis na base
        anos_opcoes = []
        try:
            conn_ano, cur_ano = oracle()
            cur_ano.execute("""
                SELECT DISTINCT ANO FROM (
                    SELECT DISTINCT TO_CHAR(ANO) AS ANO FROM OS_DADOS_VEICULOS WHERE ANO IS NOT NULL
                    UNION
                    SELECT DISTINCT TO_CHAR(ANO) AS ANO FROM clientes_frota WHERE ANO IS NOT NULL
                    UNION
                    SELECT DISTINCT TO_CHAR(ANO_MODELO) AS ANO FROM VEICULOS WHERE ANO_MODELO IS NOT NULL
                )
                ORDER BY ANO DESC
            """)
            anos_result = cur_ano.fetchall()
            anos_opcoes = [str(row[0]).strip() for row in anos_result if row[0] and str(row[0]).strip()]
            cur_ano.close()
            conn_ano.close()
        except Exception as e:
            st.error(f"Erro ao carregar anos: {e}")
        
        # Multiselect para anos
        anos_selecionados = st.sidebar.multiselect(
            "Ano do Veículo",
            options=anos_opcoes,
            placeholder="Selecione os anos..."
        )
        
        filtro_vendido = st.sidebar.selectbox("Status Vendido", ["Todos", "Vendido", "Não Vendido"])
        filtro_tipo_doc = st.sidebar.selectbox("Tipo de Cliente", ["Todos", "CPF", "CNPJ"])
        filtro_uf = st.sidebar.text_input("UF", placeholder="Ex: SP, RJ, MG...")
        filtro_cidade = st.sidebar.text_input("Cidade", placeholder="Digite o nome da cidade...")
        
        # Construção dinâmica dos filtros SQL
        filtros_sql = []
        if filtro_chassi:
            filtros_sql.append(f"AND CHASSI = '{filtro_chassi.strip()}'")
        if produtos_selecionados:
            codigos_produtos = [str(produtos_opcoes[p]) for p in produtos_selecionados]
            filtros_sql.append(f"AND COD_PRODUTO IN ({','.join(codigos_produtos)})")
        if modelos_selecionados:
            codigos_modelos = [str(modelos_opcoes[m]) for m in modelos_selecionados]
            filtros_sql.append(f"AND COD_MODELO IN ({','.join(codigos_modelos)})")
        if anos_selecionados:
            anos_str = ','.join([f"'{a}'" for a in anos_selecionados])
            filtros_sql.append(f"AND TO_CHAR(ANO) IN ({anos_str})")
        if filtro_vendido == "Vendido":
            filtros_sql.append("AND VENDIDO = 'S'")
        elif filtro_vendido == "Não Vendido":
            filtros_sql.append("AND (VENDIDO IS NULL OR VENDIDO = 'N')")
        if filtro_tipo_doc == "CPF":
            filtros_sql.append("AND LENGTH(TO_CHAR(COD_CLIENTE)) <= 11")
        elif filtro_tipo_doc == "CNPJ":
            filtros_sql.append("AND LENGTH(TO_CHAR(COD_CLIENTE)) > 11")
        if filtro_uf:
            filtros_sql.append(f"AND ENDERECO_UF = '{filtro_uf.strip().upper()}'")
        if filtro_cidade:
            filtros_sql.append(f"AND upper(ENDERECO_CIDADE) = upper('{filtro_cidade.strip()}')")
        
        filtros_where = " ".join(filtros_sql)
        
        query = f"""
        WITH base_unificada AS (
            -- 1. Dados de Oficina
            SELECT 
                os.COD_CLIENTE, 
                odv.CHASSI, 
                odv.COD_PRODUTO, 
                odv.COD_MODELO, 
                odv.ANO,
                MAX(os.data_emissao) AS ultima_passagem_oficina,
                CAST(NULL AS NUMBER) AS KM,
                CAST(NULL AS VARCHAR2(20)) AS PLACA,
                CAST(NULL AS VARCHAR2(1)) AS VENDIDO
            FROM OS_DADOS_VEICULOS odv 
            INNER JOIN os os 
                ON os.NUMERO_OS = odv.NUMERO_OS 
                AND os.COD_EMPRESA = odv.COD_EMPRESA 
            WHERE os.COD_EMPRESA IN (11, 33)
            GROUP BY
                os.COD_CLIENTE,
                odv.CHASSI, 
                odv.COD_PRODUTO, 
                odv.COD_MODELO, 
                odv.ANO
            UNION ALL
            -- 2. Dados de Clientes Frota
            SELECT 
                cf.COD_CLIENTE,
                cf.CHASSI, 
                cf.COD_PRODUTO, 
                cf.COD_MODELO, 
                cf.ANO,
                CAST(NULL AS DATE) AS ultima_passagem_oficina,
                cf.KM,
                cf.PLACA,
                cf.VENDIDO 
            FROM clientes_frota cf
            UNION ALL
            -- 3. Dados de Veículos
            SELECT 
                v.COD_CLIENTE,
                v.CHASSI_COMPLETO AS CHASSI, 
                v.COD_PRODUTO, 
                v.COD_MODELO, 
                v.ANO_MODELO AS ANO,
                CAST(NULL AS DATE) AS ultima_passagem_oficina,
                CAST(NULL AS NUMBER) AS KM,
                CAST(NULL AS VARCHAR2(20)) AS PLACA,
                CAST(NULL AS VARCHAR2(1)) AS VENDIDO
            FROM VEICULOS v 
            WHERE v.COD_EMPRESA IN (11, 33, 111)
        ),
        -- Agrupa tudo por CLIENTE e CHASSI para matar a duplicidade
        dados_agrupados AS (
            SELECT 
                COD_CLIENTE,
                CHASSI,
                MAX(COD_PRODUTO) AS COD_PRODUTO,
                MAX(COD_MODELO) AS COD_MODELO,
                MAX(ANO) AS ANO,
                MAX(ultima_passagem_oficina) AS ultima_passagem_oficina,
                MAX(KM) AS KM,
                MAX(PLACA) AS PLACA,
                MAX(VENDIDO) AS VENDIDO
            FROM base_unificada
            GROUP BY 
                COD_CLIENTE,
                CHASSI
        ),
        -- Consolida os dados e aplica a regra de prioridade de endereço
        dados_completos AS (
            SELECT 
                da.COD_CLIENTE, 
                c.NOME, 
                c.EMAIL_NFE,
                REGEXP_REPLACE(concat(c.PREFIXO_CEL, c.TELEFONE_CEL), '[^0-9]', '') AS tel_cel,
                REGEXP_REPLACE(concat(c.PREFIXO_RES, c.TELEFONE_RES), '[^0-9]', '') AS tel_residencial,
                REGEXP_REPLACE(concat(c.PREFIXO_COM, c.TELEFONE_COM), '[^0-9]', '') AS tel_comercial,
                REGEXP_REPLACE(concat(c.PREFIXO_FAX, c.TELEFONE_FAX), '[^0-9]', '') AS tel_fax,
                REGEXP_REPLACE(concat(c.PREFIXO_MSG_TXT_INST, c.NUMERO_MSG_TXT_INST), '[^0-9]', '') AS tel_whatsapp,
                -- Aplicação do COALESCE para prioridade de endereço (Residencial > Comercial > Cobrança)
                COALESCE(c.RUA_RES, c.RUA_COM, c.RUA_COBRANCA) AS ENDERECO_RUA,
                COALESCE(c.BAIRRO_RES, c.BAIRRO_COM, c.BAIRRO_COBRANCA) AS ENDERECO_BAIRRO,
                COALESCE(c.COMPLEMENTO_RES, c.COMPLEMENTO_COM, c.COMPLEMENTO_COBRANCA) AS ENDERECO_COMPLEMENTO,
                COALESCE(c.CEP_RES, c.CEP_COM, c.CEP_COBRANCA) AS ENDERECO_CEP,
                COALESCE(cir.DESCRICAO, cicom.DESCRICAO, cicob.DESCRICAO) AS ENDERECO_CIDADE,
                COALESCE(cir.UF, cicom.UF, cicob.UF) AS ENDERECO_UF,
                da.CHASSI, 
                da.COD_PRODUTO, 
                p.descricao_produto, 
                da.COD_MODELO, 
                pm.DESCRICAO_MODELO, 
                da.ANO,
                da.ultima_passagem_oficina,
                da.KM,
                da.PLACA,
                da.VENDIDO
            FROM dados_agrupados da
            LEFT JOIN produtos p ON 1=1
                AND p.COD_PRODUTO = da.COD_PRODUTO
            LEFT JOIN PRODUTOS_MODELOS pm ON 1=1
                AND pm.COD_MODELO = da.COD_MODELO
                AND pm.COD_PRODUTO = da.COD_PRODUTO 
            LEFT JOIN clientes c ON 1=1
                AND c.COD_CLIENTE = da.COD_CLIENTE 
            LEFT JOIN cidades cir ON 1=1
                AND cir.COD_CIDADES = c.COD_CID_RES
            LEFT JOIN cidades cicom ON 1=1
                AND cicom.COD_CIDADES = c.COD_CID_COM
            LEFT JOIN cidades cicob ON 1=1
                AND cicob.COD_CIDADES = c.COD_CID_COBRANCA
        )
        -- Consulta final já permitindo os filtros limpos
        SELECT * FROM dados_completos
        WHERE 1=1
            {filtros_where}
        """
        
        # Verifica se algum filtro foi aplicado
        if not filtros_sql:
            st.warning("⚠️ Por favor, aplique pelo menos um filtro para realizar a consulta. A base completa é muito grande.")
        else:
            try:
                conn_oracle, cur_oracle = oracle()
                cur_oracle.execute(query)
                result_oracle = cur_oracle.fetchall()
                columns = [desc[0] for desc in cur_oracle.description]
                df = pd.DataFrame(result_oracle, columns=columns)
                cur_oracle.close()
                conn_oracle.close()
                
                if df.empty:
                    st.info("Nenhum registro encontrado com os filtros aplicados.")
                else:
                    # Formatar data se houver
                    if 'ULTIMA_PASSAGEM_OFICINA' in df.columns:
                        df['ULTIMA_PASSAGEM_OFICINA'] = pd.to_datetime(df['ULTIMA_PASSAGEM_OFICINA'], errors='coerce')
                        df['ULTIMA_PASSAGEM_OFICINA'] = df['ULTIMA_PASSAGEM_OFICINA'].dt.strftime('%d/%m/%Y').fillna('-')
                    
                    # Substituir NaN por '-'
                    df = df.fillna('-')
                    
                    st.write(f"**Total de registros encontrados: {len(df)}**")
                    st.write(f"**Data de atualização: {datetime.now().strftime('%d/%m/%Y %H:%M')}**")
                    
                    # Botão de download
                    excel_buffer = io.BytesIO()
                    df.to_excel(excel_buffer, index=False, sheet_name="Base Clientes Veículos")
                    excel_buffer.seek(0)
                    st.download_button(
                        label="📥 Download da planilha (Excel)",
                        data=excel_buffer,
                        file_name="base_clientes_veiculos.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                    
                    # Exibir tabela
                    st.dataframe(df, hide_index=True, use_container_width=True)
                    
            except Exception as e:
                st.error(f"Erro ao executar a consulta: {e}")
    
    if menu == "IMPLANTACAO":
        st.title("Acompanhamento de Implantação de Sistemas")
        # st.info("Em construção... 🚧")
        query = f"""
        SELECT ce.COD_EMPRESA, ce.COD_EVENTO, ce.STATUS, cet.DESC_TIPO_EVENTO , ca.ANDAMENTO , cd.DESCRICAO_DESCARTE,cct.tag, ce.OBS_MEMO  
        FROM CRM_EVENTOS ce
        LEFT JOIN EMPRESAS_USUARIOS eu ON
            1 = 1
            AND eu.nome = ce.RESPONSAVEL_PELO_EVENTO
        LEFT JOIN CRM_ANDAMENTO ca ON
            1 = 1
            AND ca.COD_ANDAMENTO = ce.COD_ANDAMENTO
        LEFT JOIN MIDIA m ON
            1=1
            AND m.COD_MIDIA = ce.COD_MIDIA 
        LEFT JOIN clientes c ON
            1 = 1
            AND ce.COD_CLIENTE = c.COD_CLIENTE
        LEFT JOIN CRM_EVENTOS_TIPO cet ON 1=1
            AND cet.COD_TIPO_EVENTO = ce.COD_TIPO_EVENTO
        LEFT JOIN CRM_DESCARTES cd on 1=1
            and cd.COD_DESCARTE = ce.COD_DESCARTE
        LEFT JOIN CRM_MOTIVO_PERDAS cmp ON 1=1
            AND cmp.cod_motivo_perda = ce.cod_motivo_perda
        LEFT JOIN produtos_modelos pm ON pm.COD_PRODUTO = ce.COD_PRODUTO AND pm.COD_MODELO = ce.COD_MODELO
        LEFT JOIN caiuas_crm_tags cct ON 1=1
            AND cct.cod_empresa = ce.COD_EMPRESA 
            AND cct.cod_evento = ce.cod_evento
        WHERE 1=1
            AND ce.cod_tipo_evento=831
        """
        conn_oracle, cur_oracle = oracle()
        cur_oracle.execute(query)
        result_oracle = cur_oracle.fetchall()
        columns = [desc[0] for desc in cur_oracle.description]
        df = pd.DataFrame(result_oracle, columns=columns)
        
        # replace none to ''
        df = df.fillna('')
        
        cur_oracle.close()
        conn_oracle.close()
        
        # adiciona botão de download de planilha
        excel_buffer = io.BytesIO()
        df.to_excel(excel_buffer, index=False, sheet_name="Implantação")
        excel_buffer.seek(0)
        st.download_button(
            label="📥 Download da planilha (Excel)",
            data=excel_buffer,
            file_name="implantacao.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        st.dataframe(df, hide_index=True, use_container_width=True)
        df = df[df['STATUS'] == 'P']
        pivot = pd.pivot_table(df, index=['STATUS','ANDAMENTO','TAG'], values='COD_EVENTO', aggfunc='count').reset_index()
        st.dataframe(pivot, hide_index=True, use_container_width=True)
        
    if menu == "Leads":
        st.title("Acompanhamento de Leads")
        data_inicial_hamada = st.sidebar.date_input("Data Inicial", datetime.now().date(), key="hamada_data_inicial")
        data_final_hamada = st.sidebar.date_input("Data Final", datetime.now().date(), key="hamada_data_final")
        query = f"""
        SELECT 
            ce.COD_EMPRESA, 
            ce.COD_EVENTO,
            eu2.NOME_COMPLETO quem_criou,
            eu.NOME_COMPLETO resp_atual,
            case
                when ce.cod_empresa = 11 AND eu.nome NOT IN ('KAYLANY','STEF_HS') then 'Sorocaba'
                when ce.cod_empresa = 33 then 'Indaiatuba'
                WHEN eu.nome = 'KAYLANY' THEN 'Aquecimento'
                WHEN eu.nome = 'STEF_HS' THEN 'Aquecimento'
            end empresa,
            ce.STATUS, 
            cet.DESC_TIPO_EVENTO, 
            m.DESCRICAO midia,
            ca.ANDAMENTO, 
            cd.DESCRICAO_DESCARTE, 
            cct.tag, 
            ce.OBS_MEMO,
            to_date(ce.data_criacao) data_criacao,
            to_date(ce.data_encerramento) data_encerramento,
            (
            	SELECT to_DATE(max(ca.DATA)) FROM CRM_ACOES ca 
    			WHERE 1=1
            	AND ca.COD_EVENTO = ce.COD_EVENTO 
            	AND ca.cod_empresa = ce.cod_empresa
            	AND observacao LIKE ('Responsável pelo evento alterado para%')
            	) data_transferencia,
            to_date(ce.DATA_AGENDADA ) data_agendada,
            (
        SELECT MAX(ca_resp.RESPONSAVEL) KEEP (DENSE_RANK LAST ORDER BY ca_resp.DATA)
        FROM CRM_ACOES ca_resp
        WHERE ca_resp.COD_EVENTO = ce.COD_EVENTO
          AND ca_resp.COD_EMPRESA = ce.COD_EMPRESA
          AND ca_resp.TIPO_ACAO = 12
          AND ca_resp.OBSERVACAO LIKE 'Agendamento marcado%'
    ) responsavel_agendamento,
    (
        SELECT MIN(ca_resp.RESPONSAVEL) KEEP (DENSE_RANK LAST ORDER BY ca_resp.DATA desc)
        FROM CRM_ACOES ca_resp
        WHERE ca_resp.COD_EVENTO = ce.COD_EVENTO
          AND ca_resp.COD_EMPRESA = ce.COD_EMPRESA
          AND ca_resp.TIPO_ACAO = 12
          AND ca_resp.OBSERVACAO LIKE 'Agendamento marcado%'
    ) resp_prim_agendamento,
            to_date(cev.DATA_CRIACAO ) data_visita,
            ce.COD_EMPRESA_ANTERIOR, 
            ce.COD_EVENTO_ANTERIOR
        FROM CRM_EVENTOS ce
        LEFT JOIN EMPRESAS_USUARIOS eu ON
            1 = 1
            AND eu.nome = ce.RESPONSAVEL_PELO_EVENTO
        LEFT JOIN empresas_usuarios eu2 ON 1=1
        	AND eu2.nome = ce.criou_o_evento
        LEFT JOIN CRM_ANDAMENTO ca ON
            1 = 1
            AND ca.COD_ANDAMENTO = ce.COD_ANDAMENTO
        LEFT JOIN MIDIA m ON
            1=1
            AND m.COD_MIDIA = ce.COD_MIDIA 
        LEFT JOIN clientes c ON
            1 = 1
            AND ce.COD_CLIENTE = c.COD_CLIENTE
        LEFT JOIN CRM_EVENTOS_TIPO cet ON 1=1
            AND cet.COD_TIPO_EVENTO = ce.COD_TIPO_EVENTO
        LEFT JOIN CRM_DESCARTES cd on 1=1
            and cd.COD_DESCARTE = ce.COD_DESCARTE
        LEFT JOIN CRM_MOTIVO_PERDAS cmp ON 1=1
            AND cmp.cod_motivo_perda = ce.cod_motivo_perda
        LEFT JOIN produtos_modelos pm ON pm.COD_PRODUTO = ce.COD_PRODUTO AND pm.COD_MODELO = ce.COD_MODELO
        LEFT JOIN caiuas_crm_tags cct ON 1=1
            AND cct.cod_empresa = ce.COD_EMPRESA 
            AND cct.cod_evento = ce.cod_evento
        LEFT JOIN crm_eventos cev ON 1=1
        	AND cev.COD_EVENTO = ce.COD_EVENTO_ANTERIOR 
        	AND cev.COD_EMPRESA = ce.COD_EMPRESA_ANTERIOR 
        WHERE 1=1
            AND ce.cod_tipo_evento in (829,819,821,815,817,831)
            AND trunc(ce.DATA_CRIACAO) >= TO_DATE('{data_inicial_hamada}', 'YYYY-MM-DD')
            AND trunc(ce.DATA_CRIACAO) <= TO_DATE('{data_final_hamada}', 'YYYY-MM-DD')
            
        """
        conn_oracle, cur_oracle = oracle()
        conn_chatwoot, cur_chatwoot = chatwoot()
        cur_oracle.execute(query)
        result_oracle = cur_oracle.fetchall()
        columns = [desc[0] for desc in cur_oracle.description]
        df = pd.DataFrame(result_oracle, columns=columns, dtype=str)
        
        # replace none to ''
        df = df.fillna('')
        
        cur_oracle.close()
        conn_oracle.close()
        lista_eventos = []        
        df['link_fluxo'] = df.apply(lambda row: f"https://app.caiuas.com.br/crm/eventos/{row['COD_EMPRESA']}{row['COD_EVENTO']}", axis=1)
        # adiciona todos os link na lista
        for index, row in df.iterrows():
            lista_eventos.append(f"https://app.caiuas.com.br/crm/eventos/{row['COD_EMPRESA']}{row['COD_EVENTO']}")
        
        df['link_lead'] = df.apply(
            lambda row: f"https://app.caiuas.com.br/crm/eventos/{row['COD_EMPRESA_ANTERIOR']}{row['COD_EVENTO_ANTERIOR']}"
            if str(row['COD_EMPRESA_ANTERIOR']).strip() != '' and str(row['COD_EVENTO_ANTERIOR']).strip() != ''
            else '',
            axis=1
        )
        for index, row in df.iterrows():
            if str(row['COD_EMPRESA_ANTERIOR']).strip() != '' and str(row['COD_EVENTO_ANTERIOR']).strip() != '':
                lista_eventos.append(f"https://app.caiuas.com.br/crm/eventos/{row['COD_EMPRESA_ANTERIOR']}{row['COD_EVENTO_ANTERIOR']}")
        
        query = f"""
        SELECT DISTINCT ON (m.conversation_id)
            m.conversation_id,
            m.account_id,
        --    m.created_at,
            CASE
                WHEN entry->'changes'->0->'value'->'messages'->0->'referral'->>'source_url' IS NOT NULL
                THEN entry->'changes'->0->'value'->'messages'->0->'referral'->>'source_url'
                ELSE c.custom_attributes->>'link_campanha'
            END AS campanha,
            CASE
                WHEN entry->'changes'->0->'value'->'messages'->0->'referral'->>'evento_nbs' IS NOT NULL
                THEN entry->'changes'->0->'value'->'messages'->0->'referral'->>'evento_nbs'
                ELSE c.custom_attributes->>'evento_nbs'
            END AS evento_nbs
        FROM messages m
        LEFT JOIN whatsapp_raw_payloads wrp ON wrp.source_id = m.source_id
        CROSS JOIN LATERAL jsonb_array_elements(wrp.payload->'entry') AS entry
        LEFT JOIN conversations c ON c.id = m.conversation_id
        LEFT JOIN users u ON u.id = c.assignee_id
        WHERE 1=1
            and c.additional_attributes->>'evento_nbs' IN ({','.join([f"'{link}'" for link in lista_eventos])})
        """
        cur_chatwoot.execute(query)
        result_chatwoot = cur_chatwoot.fetchall()
        columns_chatwoot = [desc[0] for desc in cur_chatwoot.description]
        df_chatwoot = pd.DataFrame(result_chatwoot, columns=columns_chatwoot, dtype=str)
        df = df.merge(df_chatwoot, left_on='link_fluxo', right_on='evento_nbs', how='left')
        df['link_chat'] = df.apply(
            lambda row: f"https://chat.caiuas.com.br/app/accounts/{row['account_id']}/conversations/{row['conversation_id']}"
            if str(row.get('account_id', '')).strip() != '' and str(row.get('conversation_id', '')).strip() != ''
            else '',
            axis=1
        )   
        del df['evento_nbs']
        del df['account_id']
        del df['conversation_id']
        df = df.fillna('')
        df = df.replace('None', '')
        cur_chatwoot.close()
        conn_chatwoot.close()

        st.subheader("Eventos por responsável")
        df_eventos_filtrado = df[df['QUEM_CRIOU'].isin(['Stefany Cristine de Oliveira Araujo','EVELLYN KAYLANY SILVA','FRANCIELY MARCIAL DORNELAS'])]
        if df_eventos_filtrado.empty:
            st.info("Nenhum dado encontrado para o período.")
        else:
            pivot_vendedor_eventos = pd.pivot_table(df_eventos_filtrado, index='RESP_ATUAL', values='COD_EVENTO', aggfunc='count').reset_index()
            pivot_vendedor_eventos.columns = ['RESP_ATUAL', 'total_eventos']
            conv_por_resp = df[df['campanha'].str.strip() != ''].groupby('RESP_ATUAL')['campanha'].count().reset_index().rename(columns={'campanha': 'cont_conversao'})
            pivot_vendedor_eventos = pivot_vendedor_eventos.merge(conv_por_resp, on='RESP_ATUAL', how='left').fillna(0)
            pivot_vendedor_eventos['cont_conversao'] = pivot_vendedor_eventos['cont_conversao'].astype(int)
            total_row_eventos = pd.DataFrame({'RESP_ATUAL': ['Total'], 'total_eventos': [pivot_vendedor_eventos['total_eventos'].sum()], 'cont_conversao': [pivot_vendedor_eventos['cont_conversao'].sum()]})
            pivot_vendedor_eventos_total = pd.concat([pivot_vendedor_eventos, total_row_eventos], ignore_index=True)
            pivot_vendedor_eventos_total = pivot_vendedor_eventos_total.rename(columns={'RESP_ATUAL': 'Responsável', 'total_eventos': 'Total de Eventos', 'cont_conversao': 'Campanhas'})
            styled_eventos = pivot_vendedor_eventos_total.style.apply(
                lambda x: ['font-weight: bold' if x.name == len(pivot_vendedor_eventos_total) - 1 else '' for _ in x], axis=1
            )
            st.dataframe(styled_eventos, hide_index=True, use_container_width=True)

        date_cols = ['DATA_CRIACAO', 'DATA_ENCERRAMENTO', 'DATA_TRANSFERENCIA','DATA_AGENDADA','DATA_VISITA']
        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce').dt.date
        excel_buffer_planilha_eventos = io.BytesIO()
        with pd.ExcelWriter(excel_buffer_planilha_eventos, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name="Implantação")
            
            ws = writer.sheets["Implantação"]
            date_col_indices = [df.columns.get_loc(c) + 1 for c in date_cols if c in df.columns]
            for col_idx in date_col_indices:
                for row in ws.iter_rows(min_row=2, min_col=col_idx, max_col=col_idx, max_row=len(df) + 1):
                    for cell in row:
                        cell.number_format = 'DD/MM/YYYY'
            from openpyxl.worksheet.table import Table, TableStyleInfo
            tab = Table(
                displayName="TabelaHamada",
                ref=f"A1:{chr(64 + len(df.columns))}{len(df) + 1}"
            )
            tab.tableStyleInfo = TableStyleInfo(
                name="TableStyleMedium9",
                showFirstColumn=False,
                showLastColumn=False,
                showRowStripes=True,
                showColumnStripes=False
            )
            ws.add_table(tab)
        excel_buffer_planilha_eventos.seek(0)

        st.download_button(
            label="📥 Download da planilha (Excel)",
            data=excel_buffer_planilha_eventos,
            file_name="Eventos.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # st.subheader("Leads por tipo de evento")
        # contagem_tipo = (
        #     df.groupby('DESC_TIPO_EVENTO')['COD_EVENTO']
        #     .count()
        #     .reset_index()
        #     .rename(columns={'DESC_TIPO_EVENTO': 'Tipo de Evento', 'COD_EVENTO': 'Quantidade'})
        #     .sort_values('Quantidade', ascending=False)
        # )
        # st.bar_chart(contagem_tipo.set_index('Tipo de Evento')['Quantidade'])

        st.subheader("Filtrar tabela de eventos")
        fcol1, fcol2, fcol3, fcol4 = st.columns(4)
        with fcol1:
            opcoes_empresa = sorted([v for v in df['COD_EMPRESA'].unique() if v != ''])
            filtro_empresa = st.multiselect("Empresa", opcoes_empresa, key="filtro_cod_empresa")
        with fcol2:
            opcoes_tipo = sorted([v for v in df['DESC_TIPO_EVENTO'].unique() if v != ''])
            filtro_tipo = st.multiselect("Tipo de Evento", opcoes_tipo, key="filtro_tipo_evento")
        with fcol3:
            opcoes_resp = sorted([v for v in df['RESP_ATUAL'].unique() if v != ''])
            filtro_resp = st.multiselect("Responsável", opcoes_resp, key="filtro_resp_atual")
        with fcol4:
            opcoes_status = sorted([v for v in df['STATUS'].unique() if v != ''])
            filtro_status = st.multiselect("Status", opcoes_status, key="filtro_status_hamada")

        df_filtrado = df.copy()
        if filtro_empresa:
            df_filtrado = df_filtrado[df_filtrado['COD_EMPRESA'].isin(filtro_empresa)]
        if filtro_tipo:
            df_filtrado = df_filtrado[df_filtrado['DESC_TIPO_EVENTO'].isin(filtro_tipo)]
        if filtro_resp:
            df_filtrado = df_filtrado[df_filtrado['RESP_ATUAL'].isin(filtro_resp)]
        if filtro_status:
            df_filtrado = df_filtrado[df_filtrado['STATUS'].isin(filtro_status)]

        st.caption(f"{len(df_filtrado)} registro(s) exibido(s)")
        st.dataframe(
            df_filtrado,
            hide_index=True,
            use_container_width=True,
            column_config={
                "link_fluxo": st.column_config.LinkColumn("Link", display_text="Abrir"),
                "link_lead": st.column_config.LinkColumn("Lead", display_text="Abrir"),
                "campanha": st.column_config.LinkColumn("Campanha"),
                "link_chat": st.column_config.LinkColumn("Link Chat", display_text="Abrir"),
                "DATA_CRIACAO": st.column_config.DateColumn("Data Criação", format="DD/MM/YYYY"),
                "DATA_ENCERRAMENTO": st.column_config.DateColumn("Data Encerramento", format="DD/MM/YYYY"),
                "DATA_TRANSFERENCIA": st.column_config.DateColumn("Data Transferência", format="DD/MM/YYYY"),
            }
        )

    if menu == "Leads Agência":
        st.title("Acompanhamento - Campanhas (Chatwoot)")
        data_inicial_chat = st.sidebar.date_input("Data Inicial", datetime.now().date(), key="chat_data_inicial")
        data_final_chat = st.sidebar.date_input("Data Final", datetime.now().date(), key="chat_data_final")

        query_chatwoot = f"""
        SELECT DISTINCT ON (m.conversation_id)
            m.conversation_id,
            m.account_id,
            c.created_at,
            CASE
                WHEN entry->'changes'->0->'value'->'messages'->0->'referral'->>'source_url' IS NOT NULL
                THEN entry->'changes'->0->'value'->'messages'->0->'referral'->>'source_url'
                ELSE c.custom_attributes->>'link_campanha'
            END AS link_campanha,
            entry->'changes'->0->'value'->'messages'->0->'referral'->>'source_id' AS id_campanha,
            c.custom_attributes->>'evento_nbs' AS link_crm,
            u.name AS responsavel,
            c.custom_attributes,
            entry->'changes'->0->'value'->'messages'->0->'referral'->>'source_id' as source_id
        FROM messages m
        LEFT JOIN whatsapp_raw_payloads wrp ON wrp.source_id = m.source_id
        CROSS JOIN LATERAL jsonb_array_elements(wrp.payload->'entry') AS entry
        LEFT JOIN conversations c ON c.id = m.conversation_id
        LEFT JOIN users u ON u.id = c.assignee_id
        WHERE (
            entry->'changes'->0->'value'->'messages'->0->'referral' IS NOT NULL
            OR
            c.additional_attributes::text LIKE '%link_campanha%'
        )
            AND c.created_at::date >= DATE '{data_inicial_chat}'
            AND c.created_at::date <= DATE '{data_final_chat}'
        ORDER BY m.conversation_id, c.created_at
        """

        conn_chatwoot, cur_chatwoot = chatwoot()
        cur_chatwoot.execute(query_chatwoot)
        result_chatwoot = cur_chatwoot.fetchall()
        columns_chatwoot = [desc[0] for desc in cur_chatwoot.description]
        df_chatwoot = pd.DataFrame(result_chatwoot, columns=columns_chatwoot)
        cur_chatwoot.close()
        conn_chatwoot.close()

        df_chatwoot = df_chatwoot.fillna('')
        df_chatwoot = df_chatwoot.replace('None', '')
        df_chatwoot['link_chat'] = df_chatwoot.apply(
            lambda row: f"https://chat.caiuas.com.br/app/accounts/{row['account_id']}/conversations/{row['conversation_id']}"
            if str(row.get('account_id', '')).strip() != '' and str(row.get('conversation_id', '')).strip() != ''
            else '',
            axis=1
        )

        st.subheader("Chats por responsável")
        if df_chatwoot.empty or df_chatwoot['responsavel'].str.strip().eq('').all():
            st.info("Nenhum dado encontrado para o período.")
        else:
            pivot_vendedor = pd.pivot_table(df_chatwoot, index='responsavel', values='conversation_id', aggfunc='count').reset_index().rename(columns={'conversation_id': 'total_chats'})
           
            total_row_chats = pd.DataFrame({'responsavel': ['Total'], 'total_chats': [pivot_vendedor['total_chats'].sum()]})
            pivot_vendedor_total = pd.concat([pivot_vendedor, total_row_chats], ignore_index=True)
            styled_chats = pivot_vendedor_total.style.apply(
                lambda x: ['font-weight: bold' if x.name == len(pivot_vendedor_total) - 1 else '' for _ in x], axis=1
            )
            st.dataframe(styled_chats, hide_index=True, use_container_width=True)

        df_chatwoot_excel = df_chatwoot[['conversation_id','responsavel', 'created_at', 'link_campanha','source_id','link_crm','link_chat']].copy()
        df_chatwoot_excel['evento'] = df_chatwoot_excel['link_crm'].apply(lambda x: x.split('?')[0] if x.strip() != '' else '')
        df_chatwoot_excel['evento'] = df_chatwoot_excel['evento'].apply(lambda x: x.split('/')[-1] if x.strip() != '' else '')

        lista_eventos_oracle = [e for e in df_chatwoot_excel['evento'].unique() if e.strip() != '']
        if lista_eventos_oracle:
            in_clause = ','.join([f"'{e}'" for e in lista_eventos_oracle])
            query_oracle_eventos = f"""
            SELECT 
                concat(ce.COD_EMPRESA, ce.COD_EVENTO) AS evento,
                eu.NOME_COMPLETO AS responsavel_oracle,
                ca.ANDAMENTO AS andamento_atendimento,
                TO_CHAR(ce.TERMOMETRO) AS termometro,
                ce.COD_PROPOSTA
            FROM crm_eventos ce
            LEFT JOIN empresas_usuarios eu ON 1=1
                AND eu.nome = ce.RESPONSAVEL_PELO_EVENTO
            LEFT JOIN CRM_ANDAMENTO ca ON 1=1
                AND ca.COD_ANDAMENTO = ce.COD_ANDAMENTO
            WHERE concat(ce.COD_EMPRESA, ce.COD_EVENTO) IN ({in_clause})
            """
            conn_oracle_chat, cur_oracle_chat = oracle()
            cur_oracle_chat.execute(query_oracle_eventos)
            result_oracle_chat = cur_oracle_chat.fetchall()
            columns_oracle_chat = [desc[0].lower() for desc in cur_oracle_chat.description]
            cur_oracle_chat.close()
            conn_oracle_chat.close()
            df_oracle_eventos = pd.DataFrame(result_oracle_chat, columns=columns_oracle_chat, dtype=str).fillna('')
            df_chatwoot_excel = df_chatwoot_excel.merge(df_oracle_eventos[['evento', 'andamento_atendimento', 'termometro','cod_proposta']], on='evento', how='left')
            df_chatwoot_excel['andamento_atendimento'] = df_chatwoot_excel['andamento_atendimento'].fillna('')
            df_chatwoot_excel['termometro'] = df_chatwoot_excel['termometro'].fillna('').map(
                lambda v: {'1': 'Frio', '2': 'Morno', '3': 'Quente'}.get(str(v).strip(), 'Não classificado')
            )

        st.subheader("Campanhas (Chatwoot)")
        total_linhas_chatwoot = len(df_chatwoot)
        excel_buffer_chatwoot = io.BytesIO()
        df_chatwoot_excel.to_excel(excel_buffer_chatwoot, index=False, sheet_name="Chatwoot")
        excel_buffer_chatwoot.seek(0)
        st.download_button(
            label=f"📥 Download da tabela Chatwoot ({total_linhas_chatwoot} linhas)",
            data=excel_buffer_chatwoot,
            file_name=f"campanhas_chatwoot_{total_linhas_chatwoot}_linhas.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="download_chatwoot_chat"
        )
        st.dataframe(
            df_chatwoot[['conversation_id','responsavel', 'created_at', 'link_campanha', 'link_crm', 'link_chat']],
            hide_index=True,
            use_container_width=True,
            column_config={
                "link_campanha": st.column_config.LinkColumn("Link Campanha", display_text="Abrir"),
                "link_crm": st.column_config.LinkColumn("Link Evento NBS", display_text="Abrir"),
                "link_chat": st.column_config.LinkColumn("Link Chat", display_text="Abrir"),
            }
        )

    if menu == "Leads Escalera":
        st.title("Leads Escalera")
        data_inicial_chat = st.sidebar.date_input("Data Inicial", datetime.now().date(), key="escalera_data_inicial")
        data_final_chat = st.sidebar.date_input("Data Final", datetime.now().date(), key="escalera_data_final")

        query_chatwoot = f"""
        SELECT DISTINCT ON (m.conversation_id)
            m.conversation_id,
            m.account_id,
            c.created_at,
            CASE
                WHEN entry->'changes'->0->'value'->'messages'->0->'referral'->>'source_url' IS NOT NULL
                THEN entry->'changes'->0->'value'->'messages'->0->'referral'->>'source_url'
                ELSE c.custom_attributes->>'link_campanha'
            END AS link_campanha,
            entry->'changes'->0->'value'->'messages'->0->'referral'->>'source_id' AS id_campanha,
            c.custom_attributes->>'evento_nbs' AS link_crm,
            u.name AS responsavel,
            c.custom_attributes,
            entry->'changes'->0->'value'->'messages'->0->'referral'->>'source_id' as source_id
        FROM messages m
        LEFT JOIN whatsapp_raw_payloads wrp ON wrp.source_id = m.source_id
        CROSS JOIN LATERAL jsonb_array_elements(wrp.payload->'entry') AS entry
        LEFT JOIN conversations c ON c.id = m.conversation_id
        LEFT JOIN users u ON u.id = c.assignee_id
        WHERE (
            entry->'changes'->0->'value'->'messages'->0->'referral' IS NOT NULL
            OR
            c.additional_attributes::text LIKE '%link_campanha%'
        )
            AND c.created_at::date >= DATE '{data_inicial_chat}'
            AND c.created_at::date <= DATE '{data_final_chat}'
        ORDER BY m.conversation_id, c.created_at
        """

        conn_chatwoot, cur_chatwoot = chatwoot()
        cur_chatwoot.execute(query_chatwoot)
        result_chatwoot = cur_chatwoot.fetchall()
        columns_chatwoot = [desc[0] for desc in cur_chatwoot.description]
        df_chatwoot = pd.DataFrame(result_chatwoot, columns=columns_chatwoot)
        cur_chatwoot.close()
        conn_chatwoot.close()

        df_chatwoot = df_chatwoot.fillna('')
        df_chatwoot = df_chatwoot.replace('None', '')
        df_chatwoot['link_chat'] = df_chatwoot.apply(
            lambda row: f"https://chat.caiuas.com.br/app/accounts/{row['account_id']}/conversations/{row['conversation_id']}"
            if str(row.get('account_id', '')).strip() != '' and str(row.get('conversation_id', '')).strip() != ''
            else '',
            axis=1
        )

        st.subheader("Chats por responsável")
        if df_chatwoot.empty or df_chatwoot['responsavel'].str.strip().eq('').all():
            st.info("Nenhum dado encontrado para o período.")
        else:
            pivot_vendedor = pd.pivot_table(df_chatwoot, index='responsavel', values='conversation_id', aggfunc='count').reset_index().rename(columns={'conversation_id': 'total_chats'})
           
            total_row_chats = pd.DataFrame({'responsavel': ['Total'], 'total_chats': [pivot_vendedor['total_chats'].sum()]})
            pivot_vendedor_total = pd.concat([pivot_vendedor, total_row_chats], ignore_index=True)
            styled_chats = pivot_vendedor_total.style.apply(
                lambda x: ['font-weight: bold' if x.name == len(pivot_vendedor_total) - 1 else '' for _ in x], axis=1
            )
            st.dataframe(styled_chats, hide_index=True, use_container_width=True)

        df_chatwoot_excel = df_chatwoot[['conversation_id','responsavel', 'created_at', 'link_campanha','source_id','link_crm','link_chat']].copy()
        df_chatwoot_excel['evento'] = df_chatwoot_excel['link_crm'].apply(lambda x: x.split('?')[0] if x.strip() != '' else '')
        df_chatwoot_excel['evento'] = df_chatwoot_excel['evento'].apply(lambda x: x.split('/')[-1] if x.strip() != '' else '')

        lista_eventos_oracle = [e for e in df_chatwoot_excel['evento'].unique() if e.strip() != '']
        if lista_eventos_oracle:
            in_clause = ','.join([f"'{e}'" for e in lista_eventos_oracle])
            query_oracle_eventos = f"""
            SELECT 
                concat(ce.COD_EMPRESA, ce.COD_EVENTO) AS evento,
                eu.NOME_COMPLETO AS responsavel_oracle,
                ca.ANDAMENTO AS andamento_atendimento,
                TO_CHAR(ce.TERMOMETRO) AS termometro,
                ce.COD_PROPOSTA
            FROM crm_eventos ce
            LEFT JOIN empresas_usuarios eu ON 1=1
                AND eu.nome = ce.RESPONSAVEL_PELO_EVENTO
            LEFT JOIN CRM_ANDAMENTO ca ON 1=1
                AND ca.COD_ANDAMENTO = ce.COD_ANDAMENTO
            WHERE concat(ce.COD_EMPRESA, ce.COD_EVENTO) IN ({in_clause})
            """
            conn_oracle_chat, cur_oracle_chat = oracle()
            cur_oracle_chat.execute(query_oracle_eventos)
            result_oracle_chat = cur_oracle_chat.fetchall()
            columns_oracle_chat = [desc[0].lower() for desc in cur_oracle_chat.description]
            cur_oracle_chat.close()
            conn_oracle_chat.close()
            df_oracle_eventos = pd.DataFrame(result_oracle_chat, columns=columns_oracle_chat, dtype=str).fillna('')
            df_chatwoot_excel = df_chatwoot_excel.merge(df_oracle_eventos[['evento', 'andamento_atendimento', 'termometro','cod_proposta']], on='evento', how='left')
            df_chatwoot_excel['andamento_atendimento'] = df_chatwoot_excel['andamento_atendimento'].fillna('')
            df_chatwoot_excel['termometro'] = df_chatwoot_excel['termometro'].fillna('').map(
                lambda v: {'1': 'Frio', '2': 'Morno', '3': 'Quente'}.get(str(v).strip(), 'Não classificado')
            )

        st.subheader("Campanhas (Chatwoot)")
        total_linhas_chatwoot = len(df_chatwoot)
        excel_buffer_chatwoot = io.BytesIO()
        df_chatwoot_excel.to_excel(excel_buffer_chatwoot, index=False, sheet_name="Chatwoot")
        excel_buffer_chatwoot.seek(0)
        st.download_button(
            label=f"📥 Download da tabela Chatwoot ({total_linhas_chatwoot} linhas)",
            data=excel_buffer_chatwoot,
            file_name=f"campanhas_chatwoot_{total_linhas_chatwoot}_linhas.xlsx",
            key="download_chatwoot_escalera"
        )
        st.dataframe(
            df_chatwoot[['conversation_id','responsavel', 'created_at', 'link_campanha']],
            hide_index=True,
            use_container_width=True,
            column_config={
                "link_campanha": st.column_config.LinkColumn("Link Campanha", display_text="Abrir")
            }
        )

    if menu == "Acompanhamento Chat":
        st.title("Acompanhamento Chat (Chatwoot)")

        query_acomp_chat = """
        SELECT 
            COALESCE(u.name, 'Sem Responsável (Fila)') AS nome_usuario,
            COUNT(CASE 
                WHEN c.status IN (0, 2) AND c.waiting_since IS NOT NULL 
                THEN 1 
            END) AS qtd_pendentes,
            COUNT(CASE 
                WHEN c.status = 3 
                THEN 1 
            END) AS qtd_adiados,
            COUNT(CASE 
                WHEN c.status IN (0, 2) 
                     AND c.waiting_since < (NOW() - INTERVAL '2 hours') 
                THEN 1 
            END) AS qtd_atrasados
        FROM conversations c
        LEFT JOIN users u ON c.assignee_id = u.id
        WHERE c.status IN (0, 2, 3)
        GROUP BY 
            u.id, 
            u.name
        HAVING 
            COUNT(CASE WHEN c.status IN (0, 2) AND c.waiting_since IS NOT NULL THEN 1 END) > 0 OR
            COUNT(CASE WHEN c.status = 3 THEN 1 END) > 0 OR
            COUNT(CASE WHEN c.status IN (0, 2) AND c.waiting_since < (NOW() - INTERVAL '2 hours') THEN 1 END) > 0
        ORDER BY 
            qtd_atrasados DESC, 
            qtd_pendentes DESC
        """

        try:
            conn_ac, cur_ac = chatwoot()
            cur_ac.execute(query_acomp_chat)
            result_ac = cur_ac.fetchall()
            columns_ac = [desc[0] for desc in cur_ac.description]
            df_ac = pd.DataFrame(result_ac, columns=columns_ac)
            cur_ac.close()
            conn_ac.close()

            df_ac['qtd_pendentes'] = df_ac['qtd_pendentes'].astype(int)
            df_ac['qtd_adiados'] = df_ac['qtd_adiados'].astype(int)
            df_ac['qtd_atrasados'] = df_ac['qtd_atrasados'].astype(int)

            total_row = pd.DataFrame({
                'nome_usuario': ['Total'],
                'qtd_pendentes': [df_ac['qtd_pendentes'].sum()],
                'qtd_adiados': [df_ac['qtd_adiados'].sum()],
                'qtd_atrasados': [df_ac['qtd_atrasados'].sum()],
            })
            df_ac_com_total = pd.concat([df_ac, total_row], ignore_index=True)

            styled_ac = df_ac_com_total.rename(columns={
                'nome_usuario': 'Responsável',
                'qtd_pendentes': 'Pendentes',
                'qtd_adiados': 'Adiados',
                'qtd_atrasados': 'Atrasados (> 2h)',
            }).style.apply(
                lambda x: ['font-weight: bold' if x.name == len(df_ac_com_total) - 1 else '' for _ in x], axis=1
            ).applymap(
                lambda v: 'color: red; font-weight: bold' if isinstance(v, int) and v > 0 else '',
                subset=['Atrasados (> 2h)']
            )

            st.subheader("Conversas abertas por responsável")
            st.dataframe(styled_ac, hide_index=True, use_container_width=True)

        except Exception as e:
            st.error(f"Erro ao carregar dados do Chatwoot: {e}")

        # Tabela detalhada
        try:
            query_detalhe = """
            SELECT
                c.id AS conversation_id,
                c.account_id,
                COALESCE(u.name, 'Sem Responsável (Fila)') AS responsavel,
                c.created_at AT TIME ZONE 'UTC' AT TIME ZONE 'America/Sao_Paulo' AS data_inicio,
                EXTRACT(EPOCH FROM (NOW() - c.created_at AT TIME ZONE 'UTC')) / 60 AS minutos_aberto,
                c.status,
                (
                    SELECT m.message_type
                    FROM messages m
                    WHERE m.conversation_id = c.id
                    ORDER BY m.created_at DESC
                    LIMIT 1
                ) AS ultimo_tipo_mensagem
            FROM conversations c
            LEFT JOIN users u ON c.assignee_id = u.id
            WHERE c.status IN (0, 2, 3)
            ORDER BY c.created_at ASC
            """
            conn_det, cur_det = chatwoot()
            cur_det.execute(query_detalhe)
            result_det = cur_det.fetchall()
            columns_det = [desc[0] for desc in cur_det.description]
            df_det = pd.DataFrame(result_det, columns=columns_det)
            cur_det.close()
            conn_det.close()

            df_det['link_chat'] = df_det.apply(
                lambda row: f"https://chat.caiuas.com.br/app/accounts/{row['account_id']}/conversations/{row['conversation_id']}"
                if str(row.get('account_id', '')).strip() != ''
                else '',
                axis=1
            )

            def fmt_tempo(minutos):
                if minutos is None:
                    return ''
                h = int(minutos) // 60
                m = int(minutos) % 60
                return f"{h}h {m:02d}min"

            df_det['tempo_atendimento'] = df_det['minutos_aberto'].apply(fmt_tempo)

            status_map = {0: 'Aberto', 2: 'Pendente', 3: 'Adiado'}
            df_det['status_label'] = df_det['status'].map(status_map).fillna(df_det['status'].astype(str))

            # 1 = outgoing (agente), 0 = incoming (cliente)
            df_det['respondida'] = df_det['ultimo_tipo_mensagem'].apply(
                lambda v: '🟢' if v == 1 else '🔴'
            )

            st.subheader("Detalhamento das conversas")
            fcol_det1, fcol_det2 = st.columns(2)
            with fcol_det1:
                opcoes_resp_det = ['Todos'] + sorted(df_det['responsavel'].unique().tolist())
                filtro_resp_det = st.selectbox("Filtrar por responsável", opcoes_resp_det, key="ac_filtro_resp")
            with fcol_det2:
                filtro_status_det = st.selectbox("Filtrar por status", ['Todos', 'Aberto', 'Pendente', 'Adiado'], key="ac_filtro_status")

            df_det_filtrado = df_det.copy()
            if filtro_resp_det != 'Todos':
                df_det_filtrado = df_det_filtrado[df_det_filtrado['responsavel'] == filtro_resp_det]
            if filtro_status_det != 'Todos':
                df_det_filtrado = df_det_filtrado[df_det_filtrado['status_label'] == filtro_status_det]

            st.caption(f"{len(df_det_filtrado)} conversa(s)")
            st.dataframe(
                df_det_filtrado[['respondida', 'responsavel', 'status_label', 'data_inicio', 'tempo_atendimento', 'link_chat']].rename(columns={
                    'respondida': 'Resp.',
                    'responsavel': 'Responsável',
                    'status_label': 'Status',
                    'data_inicio': 'Início',
                    'tempo_atendimento': 'Tempo Aberto',
                    'link_chat': 'Link',
                }),
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Link": st.column_config.LinkColumn("Link", display_text="Abrir"),
                    "Início": st.column_config.DatetimeColumn("Início", format="DD/MM/YYYY HH:mm"),
                }
            )
        except Exception as e:
            st.error(f"Erro ao carregar detalhamento: {e}")

    if menu == "Acompanhamento Pós Vendas":
        st.title("Acompanhamento Pós Vendas")
        submenu_pv = st.sidebar.radio("Submenu", ["Eventos Abertos"], key="pv_submenu")
        data_inicial_pv = st.sidebar.date_input("Data Inicial", datetime.now().date(), key="pv_data_inicial")
        data_final_pv = st.sidebar.date_input("Data Final", datetime.now().date(), key="pv_data_final")
        empresa_pv = st.sidebar.selectbox("Empresa", ["Todos", "Indaiatuba", "Sorocaba"], key="pv_empresa")
        if empresa_pv == "Indaiatuba":
            filtro_empresa_pv = "AND ce.COD_EMPRESA = 33"
        elif empresa_pv == "Sorocaba":
            filtro_empresa_pv = "AND ce.COD_EMPRESA = 11"
        else:
            filtro_empresa_pv = ""

        if submenu_pv == "Eventos Abertos":
            st.subheader("Eventos Abertos")

        query_pv = f"""
        SELECT 
            cet.DESC_TIPO_EVENTO, 
            COUNT(CASE WHEN oa.DATA_AGENDADA IS NULL THEN 1 END) AS total_pendente,
            COUNT(CASE WHEN oa.DATA_AGENDADA IS NOT NULL THEN 1 END) AS total_agendado,
            COUNT(CASE WHEN os.NUMERO_OS IS NOT NULL THEN 1 END) AS total_com_os,
            count(*) total
        FROM CRM_EVENTOS ce 
        LEFT JOIN CRM_ANDAMENTO ca ON 1=1
            AND ca.COD_ANDAMENTO = ce.COD_ANDAMENTO
        LEFT JOIN CRM_EVENTOS_TIPO cet ON 1=1
            AND cet.COD_TIPO_EVENTO = ce.COD_TIPO_EVENTO
        LEFT JOIN EMPRESAS_USUARIOS eu ON 1=1
            AND eu.NOME = ce.RESPONSAVEL_PELO_EVENTO
        LEFT JOIN PRODUTOS_MODELOS pm ON 1=1
            AND pm.COD_MODELO = ce.COD_MODELO
        LEFT JOIN MIDIA m ON 1=1
            AND m.COD_MIDIA = ce.COD_MIDIA
        LEFT JOIN clientes c ON ce.COD_CLIENTE = c.COD_CLIENTE
        LEFT JOIN OS_AGENDA oa ON 1=1
            AND ce.COD_EMPRESA = oa.CRM_COD_EMPRESA 
            AND ce.COD_EVENTO = oa.CRM_COD_EVENTO 
        LEFT JOIN os os ON 1=1
            AND os.NUMERO_OS = oa.NUMERO_OS 
            AND os.COD_EMPRESA = oa.COD_EMPRESA 
        WHERE 1=1
        AND ce.COD_TIPO_EVENTO NOT IN (831,819,30,829,267,180,22,785,807,815,817,810,690)  
        {filtro_empresa_pv}
        AND TRUNC(
                CASE
                    WHEN ce.data_novo_contato IS NULL
                    THEN ce.data_evento
                    ELSE ce.data_novo_contato
                END
                ) >= TO_DATE('{data_inicial_pv}', 'YYYY-MM-DD')
        AND TRUNC(
                CASE
                    WHEN ce.data_novo_contato IS NULL
                    THEN ce.data_evento
                    ELSE ce.data_novo_contato
                END
                ) <= TO_DATE('{data_final_pv}', 'YYYY-MM-DD')
        AND ce.DATA_ENCERRAMENTO IS null
        GROUP BY cet.DESC_TIPO_EVENTO
        ORDER BY 1
        """

        try:
            conn_pv, cur_pv = oracle()
            cur_pv.execute(query_pv)
            result_pv = cur_pv.fetchall()
            columns_pv = [desc[0] for desc in cur_pv.description]
            df_pv = pd.DataFrame(result_pv, columns=columns_pv)
            cur_pv.close()
            conn_pv.close()

            if df_pv.empty:
                st.info("Nenhum registro encontrado para o período selecionado.")
            else:
                df_pv['TOTAL_PENDENTE'] = df_pv['TOTAL_PENDENTE'].astype(int)
                df_pv['TOTAL_AGENDADO'] = df_pv['TOTAL_AGENDADO'].astype(int)
                df_pv['TOTAL_COM_OS'] = df_pv['TOTAL_COM_OS'].astype(int)
                df_pv['TOTAL'] = df_pv['TOTAL'].astype(int)

                total_row = pd.DataFrame({
                    'DESC_TIPO_EVENTO': ['Total'],
                    'TOTAL_PENDENTE': [df_pv['TOTAL_PENDENTE'].sum()],
                    'TOTAL_AGENDADO': [df_pv['TOTAL_AGENDADO'].sum()],
                    'TOTAL_COM_OS': [df_pv['TOTAL_COM_OS'].sum()],
                    'TOTAL': [df_pv['TOTAL'].sum()]
                })
                df_pv_com_total = pd.concat([df_pv, total_row], ignore_index=True)

                styled_pv = df_pv_com_total.rename(columns={
                    'DESC_TIPO_EVENTO': 'Tipo de Evento',
                    'TOTAL_PENDENTE': 'Pendente',
                    'TOTAL_AGENDADO': 'Agendado',
                    'TOTAL_COM_OS': 'Com OS',
                    'TOTAL': 'Total'
                }).style.apply(
                    lambda x: ['font-weight: bold' if x.name == len(df_pv_com_total) - 1 else '' for _ in x], axis=1
                )

                st.write(f"**Período: {data_inicial_pv.strftime('%d/%m/%Y')} a {data_final_pv.strftime('%d/%m/%Y')}**")
                st.dataframe(styled_pv, hide_index=True, use_container_width=True)

            # --- Indicador: Total por Responsável ---
            query_pv_resp = f"""
            SELECT 
                eu.NOME_COMPLETO AS responsavel,
                COUNT(CASE WHEN oa.DATA_AGENDADA IS NULL THEN 1 END) AS total_pendente,
                COUNT(CASE WHEN oa.DATA_AGENDADA IS NOT NULL THEN 1 END) AS total_agendado,
                COUNT(CASE WHEN os.NUMERO_OS IS NOT NULL THEN 1 END) AS total_com_os,
                count(*) total
            FROM CRM_EVENTOS ce 
            LEFT JOIN CRM_ANDAMENTO ca ON 1=1
                AND ca.COD_ANDAMENTO = ce.COD_ANDAMENTO
            LEFT JOIN CRM_EVENTOS_TIPO cet ON 1=1
                AND cet.COD_TIPO_EVENTO = ce.COD_TIPO_EVENTO
            LEFT JOIN EMPRESAS_USUARIOS eu ON 1=1
                AND eu.NOME = ce.RESPONSAVEL_PELO_EVENTO
            LEFT JOIN PRODUTOS_MODELOS pm ON 1=1
                AND pm.COD_MODELO = ce.COD_MODELO
            LEFT JOIN MIDIA m ON 1=1
                AND m.COD_MIDIA = ce.COD_MIDIA
            LEFT JOIN clientes c ON ce.COD_CLIENTE = c.COD_CLIENTE
            LEFT JOIN OS_AGENDA oa ON 1=1
                AND ce.COD_EMPRESA = oa.CRM_COD_EMPRESA 
                AND ce.COD_EVENTO = oa.CRM_COD_EVENTO 
            LEFT JOIN os os ON 1=1
                AND os.NUMERO_OS = oa.NUMERO_OS 
                AND os.COD_EMPRESA = oa.COD_EMPRESA 
            WHERE 1=1
            AND ce.COD_TIPO_EVENTO NOT IN (831,819,30,829,267,180,22,785,807,815,817,810,690)  
            {filtro_empresa_pv}
            AND TRUNC(
                    CASE
                        WHEN ce.data_novo_contato IS NULL
                        THEN ce.data_evento
                        ELSE ce.data_novo_contato
                    END
                    ) >= TO_DATE('{data_inicial_pv}', 'YYYY-MM-DD')
            AND TRUNC(
                    CASE
                        WHEN ce.data_novo_contato IS NULL
                        THEN ce.data_evento
                        ELSE ce.data_novo_contato
                    END
                    ) <= TO_DATE('{data_final_pv}', 'YYYY-MM-DD')
            AND ce.DATA_ENCERRAMENTO IS null
            GROUP BY eu.NOME_COMPLETO
            ORDER BY total DESC
            """
            try:
                conn_pv2, cur_pv2 = oracle()
                cur_pv2.execute(query_pv_resp)
                result_pv2 = cur_pv2.fetchall()
                columns_pv2 = [desc[0] for desc in cur_pv2.description]
                df_pv_resp = pd.DataFrame(result_pv2, columns=columns_pv2)
                cur_pv2.close()
                conn_pv2.close()

                if not df_pv_resp.empty:
                    df_pv_resp['TOTAL_PENDENTE'] = df_pv_resp['TOTAL_PENDENTE'].astype(int)
                    df_pv_resp['TOTAL_AGENDADO'] = df_pv_resp['TOTAL_AGENDADO'].astype(int)
                    df_pv_resp['TOTAL_COM_OS'] = df_pv_resp['TOTAL_COM_OS'].astype(int)
                    df_pv_resp['TOTAL'] = df_pv_resp['TOTAL'].astype(int)

                    total_row_resp = pd.DataFrame({
                        'RESPONSAVEL': ['Total'],
                        'TOTAL_PENDENTE': [df_pv_resp['TOTAL_PENDENTE'].sum()],
                        'TOTAL_AGENDADO': [df_pv_resp['TOTAL_AGENDADO'].sum()],
                        'TOTAL_COM_OS': [df_pv_resp['TOTAL_COM_OS'].sum()],
                        'TOTAL': [df_pv_resp['TOTAL'].sum()]
                    })
                    df_pv_resp_com_total = pd.concat([df_pv_resp, total_row_resp], ignore_index=True)

                    styled_pv_resp = df_pv_resp_com_total.rename(columns={
                        'RESPONSAVEL': 'Responsável',
                        'TOTAL_PENDENTE': 'Pendente',
                        'TOTAL_AGENDADO': 'Agendado',
                        'TOTAL_COM_OS': 'Com OS',
                        'TOTAL': 'Total'
                    }).style.apply(
                        lambda x: ['font-weight: bold' if x.name == len(df_pv_resp_com_total) - 1 else '' for _ in x], axis=1
                    )

                    st.subheader("Total por Responsável")
                    st.dataframe(styled_pv_resp, hide_index=True, use_container_width=True)
            except Exception as e:
                st.error(f"Erro ao carregar totais por responsável: {e}")

            # --- Indicador: Pendentes por Tipo de Evento x Responsável ---
            query_pv_pivot = f"""
            SELECT 
                cet.DESC_TIPO_EVENTO,
                eu.NOME_COMPLETO AS responsavel,
                COUNT(CASE WHEN oa.DATA_AGENDADA IS NULL THEN 1 END) AS total_pendente
            FROM CRM_EVENTOS ce 
            LEFT JOIN CRM_EVENTOS_TIPO cet ON 1=1
                AND cet.COD_TIPO_EVENTO = ce.COD_TIPO_EVENTO
            LEFT JOIN EMPRESAS_USUARIOS eu ON 1=1
                AND eu.NOME = ce.RESPONSAVEL_PELO_EVENTO
            LEFT JOIN OS_AGENDA oa ON 1=1
                AND ce.COD_EMPRESA = oa.CRM_COD_EMPRESA 
                AND ce.COD_EVENTO = oa.CRM_COD_EVENTO 
            LEFT JOIN os os ON 1=1
                AND os.NUMERO_OS = oa.NUMERO_OS 
                AND os.COD_EMPRESA = oa.COD_EMPRESA 
            WHERE 1=1
            AND ce.COD_TIPO_EVENTO NOT IN (831,819,30,829,267,180,22,785,807,815,817,810,690)  
            {filtro_empresa_pv}
            AND TRUNC(
                    CASE
                        WHEN ce.data_novo_contato IS NULL
                        THEN ce.data_evento
                        ELSE ce.data_novo_contato
                    END
                    ) >= TO_DATE('{data_inicial_pv}', 'YYYY-MM-DD')
            AND TRUNC(
                    CASE
                        WHEN ce.data_novo_contato IS NULL
                        THEN ce.data_evento
                        ELSE ce.data_novo_contato
                    END
                    ) <= TO_DATE('{data_final_pv}', 'YYYY-MM-DD')
            AND ce.DATA_ENCERRAMENTO IS null
            GROUP BY cet.DESC_TIPO_EVENTO, eu.NOME_COMPLETO
            ORDER BY 1, 2
            """
            try:
                conn_pv3, cur_pv3 = oracle()
                cur_pv3.execute(query_pv_pivot)
                result_pv3 = cur_pv3.fetchall()
                columns_pv3 = [desc[0] for desc in cur_pv3.description]
                df_pv_pivot = pd.DataFrame(result_pv3, columns=columns_pv3)
                cur_pv3.close()
                conn_pv3.close()

                if not df_pv_pivot.empty:
                    df_pv_pivot['TOTAL_PENDENTE'] = df_pv_pivot['TOTAL_PENDENTE'].astype(int)
                    pivot = df_pv_pivot.pivot_table(
                        index='DESC_TIPO_EVENTO',
                        columns='RESPONSAVEL',
                        values='TOTAL_PENDENTE',
                        aggfunc='sum',
                        fill_value=0
                    )
                    pivot.columns.name = None
                    pivot.index.name = None
                    pivot = pivot.loc[:, (pivot != 0).any(axis=0)]
                    pivot['Total'] = pivot.sum(axis=1)
                    total_row_pivot = pivot.sum(axis=0).rename('Total')
                    pivot = pd.concat([pivot, total_row_pivot.to_frame().T])
                    pivot = pivot.reset_index().rename(columns={'index': 'Tipo de Evento'})

                    st.subheader("Pendentes por Tipo de Evento × Responsável")
                    st.dataframe(pivot, hide_index=True, use_container_width=True)
            except Exception as e:
                st.error(f"Erro ao carregar matriz de pendentes: {e}")

            # --- Indicador: Agendamento Confirmado (com OS) por Tipo de Evento x Responsável ---
            query_pv_os = f"""
            SELECT 
                cet.DESC_TIPO_EVENTO,
                eu.NOME_COMPLETO AS responsavel,
                COUNT(CASE WHEN os.NUMERO_OS IS NOT NULL THEN 1 END) AS total_com_os
            FROM CRM_EVENTOS ce 
            LEFT JOIN CRM_EVENTOS_TIPO cet ON 1=1
                AND cet.COD_TIPO_EVENTO = ce.COD_TIPO_EVENTO
            LEFT JOIN EMPRESAS_USUARIOS eu ON 1=1
                AND eu.NOME = ce.RESPONSAVEL_PELO_EVENTO
            LEFT JOIN OS_AGENDA oa ON 1=1
                AND ce.COD_EMPRESA = oa.CRM_COD_EMPRESA 
                AND ce.COD_EVENTO = oa.CRM_COD_EVENTO 
            LEFT JOIN os os ON 1=1
                AND os.NUMERO_OS = oa.NUMERO_OS 
                AND os.COD_EMPRESA = oa.COD_EMPRESA 
            WHERE 1=1
            AND ce.COD_TIPO_EVENTO NOT IN (831,819,30,829,267,180,22,785,807,815,817,810,690)  
            {filtro_empresa_pv}
            AND TRUNC(
                    CASE
                        WHEN ce.data_novo_contato IS NULL
                        THEN ce.data_evento
                        ELSE ce.data_novo_contato
                    END
                    ) >= TO_DATE('{data_inicial_pv}', 'YYYY-MM-DD')
            AND TRUNC(
                    CASE
                        WHEN ce.data_novo_contato IS NULL
                        THEN ce.data_evento
                        ELSE ce.data_novo_contato
                    END
                    ) <= TO_DATE('{data_final_pv}', 'YYYY-MM-DD')
            AND ce.DATA_ENCERRAMENTO IS null
            GROUP BY cet.DESC_TIPO_EVENTO, eu.NOME_COMPLETO
            ORDER BY 1, 2
            """
            try:
                conn_pv4, cur_pv4 = oracle()
                cur_pv4.execute(query_pv_os)
                result_pv4 = cur_pv4.fetchall()
                columns_pv4 = [desc[0] for desc in cur_pv4.description]
                df_pv_os = pd.DataFrame(result_pv4, columns=columns_pv4)
                cur_pv4.close()
                conn_pv4.close()

                if not df_pv_os.empty:
                    df_pv_os['TOTAL_COM_OS'] = df_pv_os['TOTAL_COM_OS'].astype(int)
                    pivot_os = df_pv_os.pivot_table(
                        index='DESC_TIPO_EVENTO',
                        columns='RESPONSAVEL',
                        values='TOTAL_COM_OS',
                        aggfunc='sum',
                        fill_value=0
                    )
                    pivot_os.columns.name = None
                    pivot_os.index.name = None
                    pivot_os = pivot_os.loc[:, (pivot_os != 0).any(axis=0)]
                    pivot_os['Total'] = pivot_os.sum(axis=1)
                    total_row_os = pivot_os.sum(axis=0).rename('Total')
                    pivot_os = pd.concat([pivot_os, total_row_os.to_frame().T])
                    pivot_os = pivot_os.reset_index().rename(columns={'index': 'Tipo de Evento'})

                    st.subheader("Agendamento Confirmado por Tipo de Evento × Responsável")
                    st.dataframe(pivot_os, hide_index=True, use_container_width=True)
            except Exception as e:
                st.error(f"Erro ao carregar matriz de agendamentos confirmados: {e}")

            # --- Indicador: Eventos Descartados ---
            query_pv_descartados = f"""
            SELECT 
                cmp.DESC_MOTIVO, 
                COUNT(CASE WHEN oa.DATA_AGENDADA IS NULL THEN 1 END) AS total_pendente,
                COUNT(CASE WHEN oa.DATA_AGENDADA IS NOT NULL THEN 1 END) AS total_agendado,
                count(*) total
            FROM CRM_EVENTOS ce 
            LEFT JOIN CRM_ANDAMENTO ca ON 1=1
                AND ca.COD_ANDAMENTO = ce.COD_ANDAMENTO
            LEFT JOIN CRM_EVENTOS_TIPO cet ON 1=1
                AND cet.COD_TIPO_EVENTO = ce.COD_TIPO_EVENTO
            LEFT JOIN EMPRESAS_USUARIOS eu ON 1=1
                AND eu.NOME = ce.RESPONSAVEL_PELO_EVENTO
            LEFT JOIN PRODUTOS_MODELOS pm ON 1=1
                AND pm.COD_MODELO = ce.COD_MODELO
            LEFT JOIN MIDIA m ON 1=1
                AND m.COD_MIDIA = ce.COD_MIDIA
            LEFT JOIN clientes c ON ce.COD_CLIENTE = c.COD_CLIENTE
            LEFT JOIN OS_AGENDA oa ON 1=1
                AND ce.COD_EMPRESA = oa.CRM_COD_EMPRESA 
                AND ce.COD_EVENTO = oa.CRM_COD_EVENTO 
            LEFT JOIN os os ON 1=1
                AND os.NUMERO_OS = oa.NUMERO_OS 
                AND os.COD_EMPRESA = oa.COD_EMPRESA 
            LEFT JOIN CRM_MOTIVO_PERDAS cmp ON 1=1
                AND cmp.COD_MOTIVO_PERDA = ce.COD_MOTIVO_PERDA 
            WHERE 1=1
            AND ce.COD_TIPO_EVENTO NOT IN (831,819,30,829,267,180,22,785,807,815,817,810,690)  
            {filtro_empresa_pv}
            AND TRUNC(ce.DATA_ENCERRAMENTO) >= TO_DATE('{data_inicial_pv}', 'YYYY-MM-DD')
            AND TRUNC(ce.DATA_ENCERRAMENTO) <= TO_DATE('{data_final_pv}', 'YYYY-MM-DD')
            AND cmp.DESC_MOTIVO IS NOT NULL
            GROUP BY cmp.DESC_MOTIVO  
            ORDER BY 1
            """
            try:
                conn_pv5, cur_pv5 = oracle()
                cur_pv5.execute(query_pv_descartados)
                result_pv5 = cur_pv5.fetchall()
                columns_pv5 = [desc[0] for desc in cur_pv5.description]
                df_pv_desc = pd.DataFrame(result_pv5, columns=columns_pv5)
                cur_pv5.close()
                conn_pv5.close()

                if not df_pv_desc.empty:
                    df_pv_desc['TOTAL_PENDENTE'] = df_pv_desc['TOTAL_PENDENTE'].astype(int)
                    df_pv_desc['TOTAL_AGENDADO'] = df_pv_desc['TOTAL_AGENDADO'].astype(int)
                    df_pv_desc['TOTAL'] = df_pv_desc['TOTAL'].astype(int)

                    total_row_desc = pd.DataFrame({
                        'DESC_MOTIVO': ['Total'],
                        'TOTAL_PENDENTE': [df_pv_desc['TOTAL_PENDENTE'].sum()],
                        'TOTAL_AGENDADO': [df_pv_desc['TOTAL_AGENDADO'].sum()],
                        'TOTAL': [df_pv_desc['TOTAL'].sum()]
                    })
                    df_pv_desc_com_total = pd.concat([df_pv_desc, total_row_desc], ignore_index=True)

                    styled_pv_desc = df_pv_desc_com_total.rename(columns={
                        'DESC_MOTIVO': 'Motivo',
                        'TOTAL_PENDENTE': 'Pendente',
                        'TOTAL_AGENDADO': 'Agendado',
                        'TOTAL': 'Total'
                    }).style.apply(
                        lambda x: ['font-weight: bold' if x.name == len(df_pv_desc_com_total) - 1 else '' for _ in x], axis=1
                    )

                    st.subheader("Eventos Descartados")
                    st.dataframe(styled_pv_desc, hide_index=True, use_container_width=True)
            except Exception as e:
                st.error(f"Erro ao carregar eventos descartados: {e}")

            # --- Indicador: Descartes por Motivo x Responsável ---
            query_pv_desc_pivot = f"""
            SELECT 
                cmp.DESC_MOTIVO,
                eu.NOME_COMPLETO AS responsavel,
                count(*) AS total
            FROM CRM_EVENTOS ce 
            LEFT JOIN CRM_EVENTOS_TIPO cet ON 1=1
                AND cet.COD_TIPO_EVENTO = ce.COD_TIPO_EVENTO
            LEFT JOIN EMPRESAS_USUARIOS eu ON 1=1
                AND eu.NOME = ce.RESPONSAVEL_PELO_EVENTO
            LEFT JOIN OS_AGENDA oa ON 1=1
                AND ce.COD_EMPRESA = oa.CRM_COD_EMPRESA 
                AND ce.COD_EVENTO = oa.CRM_COD_EVENTO 
            LEFT JOIN os os ON 1=1
                AND os.NUMERO_OS = oa.NUMERO_OS 
                AND os.COD_EMPRESA = oa.COD_EMPRESA 
            LEFT JOIN CRM_MOTIVO_PERDAS cmp ON 1=1
                AND cmp.COD_MOTIVO_PERDA = ce.COD_MOTIVO_PERDA 
            WHERE 1=1
            AND ce.COD_TIPO_EVENTO NOT IN (831,819,30,829,267,180,22,785,807,815,817,810,690)  
            {filtro_empresa_pv}
            AND TRUNC(ce.DATA_ENCERRAMENTO) >= TO_DATE('{data_inicial_pv}', 'YYYY-MM-DD')
            AND TRUNC(ce.DATA_ENCERRAMENTO) <= TO_DATE('{data_final_pv}', 'YYYY-MM-DD')
            AND cmp.DESC_MOTIVO IS NOT NULL
            AND eu.NOME_COMPLETO IS NOT NULL
            GROUP BY cmp.DESC_MOTIVO, eu.NOME_COMPLETO
            ORDER BY 1, 2
            """
            try:
                conn_pv6, cur_pv6 = oracle()
                cur_pv6.execute(query_pv_desc_pivot)
                result_pv6 = cur_pv6.fetchall()
                columns_pv6 = [desc[0] for desc in cur_pv6.description]
                df_pv_desc_piv = pd.DataFrame(result_pv6, columns=columns_pv6)
                cur_pv6.close()
                conn_pv6.close()

                if not df_pv_desc_piv.empty:
                    df_pv_desc_piv['TOTAL'] = df_pv_desc_piv['TOTAL'].astype(int)
                    pivot_desc = df_pv_desc_piv.pivot_table(
                        index='DESC_MOTIVO',
                        columns='RESPONSAVEL',
                        values='TOTAL',
                        aggfunc='sum',
                        fill_value=0
                    )
                    pivot_desc.columns.name = None
                    pivot_desc.index.name = None
                    pivot_desc = pivot_desc.loc[:, (pivot_desc != 0).any(axis=0)]
                    pivot_desc['Total'] = pivot_desc.sum(axis=1)
                    total_row_desc_piv = pivot_desc.sum(axis=0).rename('Total')
                    pivot_desc = pd.concat([pivot_desc, total_row_desc_piv.to_frame().T])
                    pivot_desc = pivot_desc.reset_index().rename(columns={'index': 'Motivo'})

                    styled_desc_piv = pivot_desc.style.apply(
                        lambda x: ['font-weight: bold' if x.name == len(pivot_desc) - 1 else '' for _ in x], axis=1
                    )

                    st.subheader("Descartes por Motivo × Responsável")
                    st.dataframe(styled_desc_piv, hide_index=True, use_container_width=True)
            except Exception as e:
                st.error(f"Erro ao carregar matriz de descartes: {e}")

            # --- Tabela Detalhada ---
            query_pv_detalhe = f"""
            SELECT 
                ce.COD_EMPRESA,
                ce.COD_EVENTO,
                TRUNC(
                    CASE
                        WHEN ce.DATA_NOVO_CONTATO IS NULL
                        THEN ce.DATA_EVENTO
                        ELSE ce.DATA_NOVO_CONTATO
                    END
                ) AS DATA_CONTATO,
                TRUNC(ce.DATA_CRIACAO) AS DATA_CRIACAO,
                TRUNC(ce.DATA_ENCERRAMENTO) AS DATA_ENCERRAMENTO,
                ce.STATUS,
                eu.NOME_COMPLETO AS NOME_RESPONSAVEL,
                cmp.DESC_MOTIVO AS MOTIVO_DESCARTE,
                oa.NUMERO_OS,
                oa.COD_OS_AGENDA
            FROM CRM_EVENTOS ce 
            LEFT JOIN CRM_EVENTOS_TIPO cet ON 1=1
                AND cet.COD_TIPO_EVENTO = ce.COD_TIPO_EVENTO
            LEFT JOIN EMPRESAS_USUARIOS eu ON 1=1
                AND eu.NOME = ce.RESPONSAVEL_PELO_EVENTO
            LEFT JOIN OS_AGENDA oa ON 1=1
                AND oa.CRM_COD_EMPRESA = ce.COD_EMPRESA
                AND oa.CRM_COD_EVENTO = ce.COD_EVENTO
            LEFT JOIN os os ON 1=1
                AND os.NUMERO_OS = oa.NUMERO_OS 
                AND os.COD_EMPRESA = oa.COD_EMPRESA 
            LEFT JOIN CRM_MOTIVO_PERDAS cmp ON 1=1
                AND cmp.COD_MOTIVO_PERDA = ce.COD_MOTIVO_PERDA 
            WHERE 1=1
            AND ce.COD_TIPO_EVENTO NOT IN (831,819,30,829,267,180,22,785,807,815,817,810,690)  
            {filtro_empresa_pv}
            AND TRUNC(
                    CASE
                        WHEN ce.DATA_NOVO_CONTATO IS NULL
                        THEN ce.DATA_EVENTO
                        ELSE ce.DATA_NOVO_CONTATO
                    END
                    ) >= TO_DATE('{data_inicial_pv}', 'YYYY-MM-DD')
            AND TRUNC(
                    CASE
                        WHEN ce.DATA_NOVO_CONTATO IS NULL
                        THEN ce.DATA_EVENTO
                        ELSE ce.DATA_NOVO_CONTATO
                    END
                    ) <= TO_DATE('{data_final_pv}', 'YYYY-MM-DD')
            ORDER BY DATA_CONTATO DESC
            """
            try:
                conn_pv7, cur_pv7 = oracle()
                cur_pv7.execute(query_pv_detalhe)
                result_pv7 = cur_pv7.fetchall()
                columns_pv7 = [desc[0] for desc in cur_pv7.description]
                df_pv_det = pd.DataFrame(result_pv7, columns=columns_pv7)
                cur_pv7.close()
                conn_pv7.close()

                if not df_pv_det.empty:
                    df_pv_det['DATA_CONTATO'] = pd.to_datetime(df_pv_det['DATA_CONTATO'], errors='coerce').dt.strftime('%d/%m/%Y').fillna('-')
                    df_pv_det['DATA_CRIACAO'] = pd.to_datetime(df_pv_det['DATA_CRIACAO'], errors='coerce').dt.strftime('%d/%m/%Y').fillna('-')
                    df_pv_det['DATA_ENCERRAMENTO'] = pd.to_datetime(df_pv_det['DATA_ENCERRAMENTO'], errors='coerce').dt.strftime('%d/%m/%Y').fillna('-')
                    df_pv_det = df_pv_det.fillna('-')
                    df_pv_det['LINK'] = df_pv_det.apply(
                        lambda row: f"https://app.caiuas.com.br/crm/eventos/{row['COD_EMPRESA']}{row['COD_EVENTO']}", axis=1
                    )

                    st.subheader("Planilha Detalhada")
                    st.dataframe(
                        df_pv_det.rename(columns={
                            'COD_EMPRESA': 'Empresa',
                            'COD_EVENTO': 'Evento',
                            'DATA_CONTATO': 'Data Contato',
                            'DATA_CRIACAO': 'Data Criação',
                            'DATA_ENCERRAMENTO': 'Data Encerramento',
                            'STATUS': 'Status',
                            'NOME_RESPONSAVEL': 'Responsável',
                            'MOTIVO_DESCARTE': 'Motivo Descarte',
                            'NUMERO_OS': 'Nº OS',
                            'COD_AGENDA': 'Cód Agenda',
                            'LINK': 'Evento NBS',
                        }),
                        hide_index=True,
                        use_container_width=True,
                        column_config={
                            "Evento NBS": st.column_config.LinkColumn("Evento NBS", display_text="Abrir"),
                        }
                    )
            except Exception as e:
                st.error(f"Erro ao carregar planilha detalhada: {e}")

        except Exception as e:
            st.error(f"Erro ao executar a consulta: {e}")

    if menu == "Acompanhamento Diário":
        st.title("Acompanhamento Diário")
        data_inicial_ad = st.sidebar.date_input("Data Inicial", datetime.now().date(), key="ad_data_inicial")
        data_final_ad = st.sidebar.date_input("Data Final", datetime.now().date(), key="ad_data_final")
        empresa_ad = st.sidebar.selectbox("Filtrar por empresa", ["Todas", "11", "33"], key="ad_empresa")
        filtro_empresa_ad = f"AND eu.cod_empresa = {empresa_ad}" if empresa_ad != "Todas" else ""

        from dateutil.relativedelta import relativedelta
        data_inicial_anterior = data_inicial_ad - relativedelta(months=1)
        data_final_anterior = data_final_ad - relativedelta(months=1)

        try:
            conn_oracle, cur_oracle = oracle()
            conn_chat, cur_chat = chatwoot()
            
            # Conversões Marketing - CHAT
            query = f"""
                SELECT DISTINCT ON (m.conversation_id)
                    c.created_at,
                    CASE
                        WHEN entry->'changes'->0->'value'->'messages'->0->'referral'->>'source_url' IS NOT NULL
                        THEN entry->'changes'->0->'value'->'messages'->0->'referral'->>'source_url'
                        ELSE c.custom_attributes->>'link_campanha'
                    END AS link_campanha,
                    --entry->'changes'->0->'value'->'messages'->0->'referral'->>'source_id' AS id_campanha,
                    c.custom_attributes->>'evento_nbs' AS link_crm,
                    u.name AS responsavel
                FROM messages m
                LEFT JOIN whatsapp_raw_payloads wrp ON wrp.source_id = m.source_id
                CROSS JOIN LATERAL jsonb_array_elements(wrp.payload->'entry') AS entry
                LEFT JOIN conversations c ON c.id = m.conversation_id
                LEFT JOIN users u ON u.id = c.assignee_id
                WHERE (
                    entry->'changes'->0->'value'->'messages'->0->'referral' IS NOT NULL
                    OR
                    c.additional_attributes::text LIKE '%link_campanha%'
                )
                    AND c.created_at::date >= DATE '{data_inicial_ad}'
                    AND c.created_at::date <= DATE '{data_final_ad}'
                ORDER BY m.conversation_id, c.created_at
            """
            cur_chat.execute(query)
            conversoes_marketing = cur_chat.fetchall()
            conversoes_marketing = pd.DataFrame(conversoes_marketing, columns=[desc[0] for desc in cur_chat.description])
            
            def _parse_campanha(link):
                if not link or str(link).strip() == '':
                    return ''
                from urllib.parse import urlparse, parse_qs
                parsed = urlparse(str(link))
                if 'hondacaiuas.com.br' not in parsed.netloc:
                    return str(link)
                qs = parse_qs(parsed.query)
                source = qs.get('utm_source', [''])[0]
                if source.lower() == 'chatgpt.com':
                    return 'CHATGPT'
                campaign = qs.get('utm_campaign', [''])[0]
                if not campaign:
                    campaign = 'performance-max'
                if source or campaign:
                    return f"{source}-{campaign}".lower()
                return str(link)
            
            conversoes_marketing['campanha'] = conversoes_marketing['link_campanha'].apply(_parse_campanha)

            # Remove links hondacaiuas.com.br sem utm_source nem gclid
            def _tem_rastreamento(link):
                if not link or str(link).strip() == '':
                    return True
                l = str(link)
                if 'hondacaiuas.com.br' not in l:
                    return True
                return 'utm_source' in l or 'gl_' in l

            conversoes_marketing = conversoes_marketing[conversoes_marketing['link_campanha'].apply(_tem_rastreamento)]
            conversoes_marketing['evento'] = conversoes_marketing['link_crm'].str.extract(r'eventos/(\d+)').astype(str)
            conversoes_marketing = conversoes_marketing.fillna('')
            conversoes_marketing['evento'] = conversoes_marketing['evento'].apply(lambda x: x if x.isdigit() else '')
            lista_eventos = [e.strip() for e in conversoes_marketing['evento'].tolist() if e and str(e).strip() not in ('', 'nan', 'None', 'NaN')]
            
            st.write(f"Total de conversões encontradas: {len(conversoes_marketing)}")
            st.dataframe(conversoes_marketing)
            
            # Propostas geradas para as conversões
            query = f"""
                SELECT 
                to_char(concat(cre.cod_empresa, cre.cod_evento)) evento,
                to_char(v.COD_PROPOSTA) COD_PROPOSTA, 
                vp.EMISSAO data_proposta, 
                vp.VENDEDOR cod_vendedor, 
                eu.NOME_COMPLETO nome_vendedor, 
                pm.DESCRICAO_MODELO modelo, 
                cor.DESCRICAO cor, 
                v.ANO_MODELO, 
                v.CHASSI_COMPLETO, 
                e.NOME empresa, 
                v.DATA_NOTA emissao,
                p.DESCRICAO patio,
                c.COD_CLIENTE, 
                c.NOME nome_cliente,
                CASE 
                    WHEN v.novo_usado = 'U' THEN 'Usado'
                    WHEN v.COD_PROPOSTA_INTERNET IS NOT NULL THEN 'Direta'
                    ELSE 'Novo'
                END novo_usado,
                cf.PLACA,
                CASE
                    WHEN c.COD_CID_COM <> NULL THEN cid_com.DESCRICAO
                    WHEN c.COD_CID_RES <> NULL THEN cid_res.DESCRICAO 
                    ELSE cid_cob.DESCRICAO 
                END cidade,
                to_char(ve.CONTROLE) numero_nota
            FROM veiculos v 
            LEFT JOIN produtos pr ON pr.COD_PRODUTO = v.COD_PRODUTO 
            LEFT JOIN CORES_EXTERNAS cor ON cor.COR_EXTERNA = v.COR_EXTERNA 
            LEFT JOIN produtos_modelos pm ON pm.COD_PRODUTO = v.COD_PRODUTO AND pm.COD_MODELO = v.COD_MODELO 
            LEFT JOIN VEICULOS_PROPOSTAS vp ON vp.CHASSI_RESUMIDO = v.CHASSI_RESUMIDO AND vp.STATUS_PROPOSTA <> 'C'
            LEFT JOIN clientes c ON c.COD_CLIENTE = vp.COD_CLIENTE 
            LEFT JOIN patio p ON p.COD_PATIO = v.COD_PATIO
            LEFT JOIN EMPRESAS_USUARIOS eu ON eu.NOME = vp.VENDEDOR 
            LEFT JOIN empresas_usuarios eu2 ON eu2.nome = vp.QUEM_APROVOU 
            LEFT JOIN empresas e ON e.cod_empresa = v.COD_EMPRESA
            LEFT JOIN CLIENTES_FROTA cf ON cf.chassi = v.CHASSI_COMPLETO AND cf.COD_CLIENTE = c.COD_CLIENTE AND cf.nome = vp.VENDEDOR 
            LEFT JOIN cidades cid_res ON cid_res.cod_cidades = c.COD_CID_RES AND cid_res.uf = c.UF_RES 
            LEFT JOIN cidades cid_com ON cid_com.cod_cidades = c.COD_CID_COM AND cid_com.uf = c.UF_COM 
            LEFT JOIN cidades cid_cob ON cid_cob.cod_cidades = c.COD_CID_COBRANCA AND cid_cob.uf = c.UF_COBRANCA 
            LEFT JOIN vendas ve ON 1=1
                AND ve.COD_PROPOSTA = v.COD_PROPOSTA 
                AND ve.STATUS = 0
            LEFT JOIN crm_eventos cre ON 1=1
                AND cre.status <> 'D'
                AND cre.COD_PROPOSTA = vp.COD_PROPOSTA
                AND cre.COD_TIPO_EVENTO IN (819,821,815,817,810,812,829,831,795,793,797,799,787,833,825,785,807,827,823)
            WHERE 1=1
                and v.status in ('V','A')
                AND concat(cre.cod_empresa, cre.cod_evento) in ({','.join([str(e) for e in lista_eventos])})
            ORDER BY pm.DESCRICAO_MODELO
            """ if lista_eventos else None
            if lista_eventos:
                cur_oracle.execute(query)
                propostas_conversoes = cur_oracle.fetchall()
                propostas_conversoes = pd.DataFrame(propostas_conversoes, columns=[desc[0] for desc in cur_oracle.description], dtype=str)
                propostas_conversoes.columns = propostas_conversoes.columns.str.lower()
            else:
                propostas_conversoes = pd.DataFrame(columns=['evento'])
                
            st.write(f"Total de propostas relacionadas às conversões: {len(propostas_conversoes)}")
            st.dataframe(propostas_conversoes)
            
            
            cur_oracle.close()
            conn_oracle.close()


        except Exception as e:
            st.error(f"Erro ao executar a consulta: {e}")

    if st.sidebar.button("Sair", width="stretch"):
        st.query_params.clear()
        st.session_state.clear()
        st.rerun()