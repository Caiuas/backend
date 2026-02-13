
import streamlit as st
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
import jwt

BRAZIL_TZ = pytz.timezone('America/Sao_Paulo')  # UTC-3

def get_brazil_now():
    """Retorna datetime atual no timezone do Brasil"""
    return datetime.now(BRAZIL_TZ)    
st.set_page_config(
    page_title="BI - Caiuás",
    page_icon="📊",
    layout="wide"
)

# def check_password(plain_password, hashed_password):
#     return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

# # @st.cache(allow_output_mutation=True)
# def get_cookie_manager():
#     return stx.CookieManager()

# cookies = get_cookie_manager()

# if 'logged_in' not in st.session_state:
#     # Tenta recuperar o estado do login a partir do cookie
#     cookie_value = cookies.get('caiuas_bi_auth_token')
#     if cookie_value is not None:
#         # Em um app real, você validaria este token
#         if cookie_value == "logged_in_user_token_value":
#             st.session_state['logged_in'] = True
#         else:
#             st.session_state['logged_in'] = False
#     else:
#         st.session_state['logged_in'] = False

# def login(message):
#     """Exibe o formulário de login."""
#     st.title("Login")
#     if message != None:
#         st.error(message)
#     with st.form("login_form"):
#         username = st.text_input("Usuário")
#         password = st.text_input("Senha", type="password")
#         submitted = st.form_submit_button("Entrar")
#         if submitted:
#             query = f"""
#                 select name,encrypted_password 
#                 from users
#                 where 1=1
#                     and lower(email) = '{str(username).lower()}'
#             """
#             conn_chatwoot, cur_chatwoot = chatwoot()
#             cur_chatwoot.execute(query)
#             user = cur_chatwoot.fetchone()
#             cur_chatwoot.close()
            
#             # Verifica se o usuário foi encontrado
#             if user is None:
#                 st.session_state['login_error'] = "Usuário ou senha inválidos"
#                 st.rerun()
#                 return
                
#             if check_password(password, user[1]):
#                 now_brazil = get_brazil_now()
#                 exp_time = now_brazil + timedelta(days=1)
#                 payload = {
#                         # "email": email,
#                         "name": username,
#                         'exp': int(exp_time.timestamp()),
#                         'iat': int(now_brazil.timestamp()),
#                         'nbf': int(now_brazil.timestamp()),
#                         'iss': os.environ.get('APP_URL'),
#                     }
#                 token = jwt.encode(payload, os.environ.get('SECRET_KEY_BASE'), algorithm='HS256')
#                 # <-- NOVO: Define o cookie
#                 cookies.set('token', token, expires_at=datetime.now() + timedelta(days=1))                
               
#                 st.session_state['logged_in'] = True
#                 # Limpa qualquer erro de login anterior
#                 if 'login_error' in st.session_state:
#                     del st.session_state['login_error']
#                 st.rerun()
#             else:
#                 st.session_state['login_error'] = "Usuário ou senha inválidos"
#                 st.rerun()

# def logout():
#     """Função para fazer logout."""
#     # <-- NOVO: Deleta o cookie
#     cookies.delete('token')
#     # Deleta o estado da sessão
#     if 'logged_in' in st.session_state:
#         del st.session_state['logged_in']
#     st.rerun()

# token = cookies.get('caiuas_bi_auth_token')

# if not st.session_state.get("logged_in", False):
# # if 
#     # remove cookies e redireciona para pagina de login
#     # cookies.delete('caiuas_bi_auth_token')
#     login(None)
#     st.stop()

# st.sidebar.button("Sair", on_click=logout)

menu = st.sidebar.radio(
    "Menu",
    ["inicio","Veículos","Estoque de peças","Obsolescência de estoque","CRM"]
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
    
        
        
elif menu == "Veículos":
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
    
    
    