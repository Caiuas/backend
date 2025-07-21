
import streamlit as st
from database import oracle
from datetime import datetime
import pandas as pd

def login():
    st.title("Login")
    username = st.text_input("Usuário")
    password = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if username == "admin" and password == "1234":
            st.session_state["logged_in"] = True
        else:
            st.error("Usuário ou senha inválidos")

# if "logged_in" not in st.session_state or not st.session_state["logged_in"]:
#     login()
#     st.stop()
    
st.set_page_config(
    page_title="BI - Caiuás",
    page_icon="📊",
    layout="wide"
)

menu = st.sidebar.radio(
    "Menu",
    ["Veículos","Estoque de peças","Obsolescência de estoque"]
)

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
    
    
    
    
    
    
elif menu == "Veículos":
    st.title("Acompanhamento de veículos")
    st.info("Em breve...")