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

EMAILS_ESTOQUE_PECAS = [
    "pablo.ti@caiuas.com.br",
]


def render():
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
    