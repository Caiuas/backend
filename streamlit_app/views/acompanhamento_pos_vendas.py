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

EMAILS_POS_VENDAS = [
    "pablo.ti@caiuas.com.br",
    "cristiane.aguilar@caiuas.com.br","nathalli.pereira@caiuas.com.br",
]


def render():
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
    