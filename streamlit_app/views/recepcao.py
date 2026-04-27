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

EMAILS_RECEPCAO = [
    "pablo.ti@caiuas.com.br",
    "mirela.novaga@caiuas.com.br",
    "Isadora.fraga@caiuas.com.br"
]


def render():
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
     