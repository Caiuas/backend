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

EMAILS_VEICULOS = [
    "pablo.ti@caiuas.com.br",
]


def render():
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
    