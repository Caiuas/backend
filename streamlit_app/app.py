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

# 1. Configuração da página
st.set_page_config(page_title="Caiuás - Acesso Rápido",layout="wide")

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
        st.session_state.token = url_token
    else:
        # Se o token na URL expirou, limpa a URL
        st.query_params.clear()
        st.session_state.authenticated = False

# --- INTERFACE ---

if not st.session_state.get("authenticated"):
    st.image("https://caiuas.com.br/wp-content/uploads/2021/05/logo-caiuas.png")
    st.title("Acesso ao Sistema")
    
    
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
    menu = st.sidebar.radio(
        "Menu",
        ["RECEPCAO","CRM SHOWROOM","inicio","Veículos","Estoque de peças","Obsolescência de estoque","CRM","Base Clientes/Veículos"]
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

    if menu == "CRM SHOWROOM":
        st.title("Acompanhamento de CRM - Showroom")
        # st.write("Em desenvolvimento...")
        data_inicial = st.sidebar.date_input("Data Inicial", datetime.now())
        data_final = st.sidebar.date_input("Data Final", datetime.now())
        query = f"""
            SELECT 
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
                    AND ce.COD_TIPO_EVENTO IN (819,821,825,785,807,827,815,817,823,810,812)
                    AND TRUNC(ce.DATA_CRIACAO) >= TO_DATE('{data_inicial}', 'YYYY-MM-DD') AND TRUNC(ce.DATA_CRIACAO) <= TO_DATE('{data_final}', 'YYYY-MM-DD')
        """
        con, cur = oracle()
        cur.execute(query)
        results = cur.fetchall()
        df = pd.DataFrame(results, columns=[desc[0] for desc in cur.description])
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
        
        excel_buffer = io.BytesIO()
        df.to_excel(excel_buffer, index=False, sheet_name="Eventos CRM Showroom")
        excel_buffer.seek(0)
        st.download_button(
            label="Download da planilha de eventos",
            data=excel_buffer,
            file_name="eventos_crm_showroom.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
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
                yaxis={'categoryorder': 'total ascending'},
                height=400
            )
            st.plotly_chart(fig_veiculo, use_container_width=True)
        # divisor para mais tre colunas
        st.markdown("---")
        col4, col5, col6 = st.columns(3)
        with col4:
            # nada
            st.empty()
        with col5:
            st.empty()
        with col6:
            st.empty()
            
        
        
        st.subheader("Detalhes dos eventos")
        st.dataframe(
            df, 
            hide_index=True,
            column_config={
                "LINK": st.column_config.LinkColumn(
                    "Abrir Evento",
                    display_text="Abrir"
                )
            }
        )  
    
    if menu == "RECEPCAO":
        st.title("Acompanhamento - Fluxo de loja")
        # st.write("Em desenvolvimento...")
        data_inicial = st.sidebar.date_input("Data Inicial", datetime.now())
        data_final = st.sidebar.date_input("Data Final", datetime.now())
        query = f"""
            SELECT 
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
                    AND ce.COD_TIPO_EVENTO IN (819,821,825,785,807,827,815,817,823,810,812)
                    AND TRUNC(ce.DATA_CRIACAO) >= TO_DATE('{data_inicial}', 'YYYY-MM-DD') AND TRUNC(ce.DATA_CRIACAO) <= TO_DATE('{data_final}', 'YYYY-MM-DD')
        """
        con, cur = oracle()
        cur.execute(query)
        results = cur.fetchall()
        df = pd.DataFrame(results, columns=[desc[0] for desc in cur.description])
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
        
    if st.sidebar.button("Sair", width="stretch"):
        st.query_params.clear()
        st.session_state.clear()
        st.rerun()