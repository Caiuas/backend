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

EMAILS_POS_VENDAS2 = [
    "pablo.ti@caiuas.com.br",
    "debora.horvath@caiuas.com.br",
    "cristiane.aguilar@caiuas.com.br"
]


def render():
    st.title("Ciclo de veículos")
    submenu_pv = st.sidebar.radio("Submenu", ["Eventos Abertos"], key="ciclo_veiculos_submenu")
    data_final_pv = st.sidebar.date_input("Data Final", datetime.now().date(), key="ciclo_veiculos_data_final")
    data_inicial_pv = st.sidebar.date_input("Data Inicial", data_final_pv - timedelta(days=30), key="ciclo_veiculos_data_inicial")
    empresa_pv = st.sidebar.selectbox("Empresa", ["Todos", "Indaiatuba", "Sorocaba"], key="ciclo_veiculos_empresa")
    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d") 
    if data_inicial_pv > data_final_pv:
        st.warning("Data Inicial não pode ser maior que a Data Final.")
        return
    if empresa_pv == "Indaiatuba":
        filtro_empresa_pv = "AND ce.COD_EMPRESA = 33"
    elif empresa_pv == "Sorocaba":
        filtro_empresa_pv = "AND ce.COD_EMPRESA = 11"
    else:
        filtro_empresa_pv = ""
    
    if submenu_pv == "Eventos Abertos":
        st.subheader("Eventos Abertos")

    df_detalhamento_abertos = pd.DataFrame()
    df_detalhamento_encerrados = pd.DataFrame()
    df_detalhamento_descartados = pd.DataFrame()
    
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
    AND ce.COD_EMPRESA IN (11,33)
    AND ce.COD_TIPO_EVENTO IN (8,
    755,
    789,
    446,
    776,
    715,
    448,
    429,
    430,
    431,
    753,
    772,
    774,
    717,
    719,
    721,
    723,
    725,
    727,
    769,
    778,
    780)  
    and ce.status in ('P','A')
    AND TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) <=
        TO_DATE('{now_str}', 'YYYY-MM-DD' )
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

            df_export_pv = df_pv_com_total.rename(columns={
                'DESC_TIPO_EVENTO': 'Tipo de Evento',
                'TOTAL_PENDENTE': 'Pendente',
                'TOTAL_AGENDADO': 'Agendado',
                'TOTAL_COM_OS': 'Com OS',
                'TOTAL': 'Total'
            })
            df_detalhamento_abertos = df_export_pv.copy()
            buffer_excel_pv = io.BytesIO()
            with pd.ExcelWriter(buffer_excel_pv, engine='xlsxwriter') as writer:
                df_export_pv.to_excel(writer, index=False, sheet_name='Ciclo de veículos')
            buffer_excel_pv.seek(0)

            st.download_button(
                label='Baixar Excel',
                data=buffer_excel_pv,
                file_name=f"ciclo_veiculos_{data_inicial_pv.strftime('%Y%m%d')}_{data_final_pv.strftime('%Y%m%d')}.xlsx",
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
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
        AND ce.COD_EMPRESA IN (11,33)
        AND ce.COD_TIPO_EVENTO IN (8,
            755,
            789,
            446,
            776,
            715,
            448,
            429,
            430,
            431,
            753,
            772,
            774,
            717,
            719,
            721,
            723,
            725,
            727,
            769,
            778,
            780)  
            and ce.status in ('P','A')
            AND TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) <=
        TO_DATE('{now_str}', 'YYYY-MM-DD' )
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
                df_export_pv_resp = df_pv_resp_com_total.rename(columns={
                    'RESPONSAVEL': 'Responsável',
                    'TOTAL_PENDENTE': 'Pendente',
                    'TOTAL_AGENDADO': 'Agendado',
                    'TOTAL_COM_OS': 'Com OS',
                    'TOTAL': 'Total'
                })
                buffer_excel_pv_resp = io.BytesIO()
                with pd.ExcelWriter(buffer_excel_pv_resp, engine='xlsxwriter') as writer:
                    df_export_pv_resp.to_excel(writer, index=False, sheet_name='Total por Responsável')
                buffer_excel_pv_resp.seek(0)

                st.download_button(
                    label='Baixar Excel por Responsável',
                    data=buffer_excel_pv_resp.getvalue(),
                    file_name=f"ciclo_veiculos_responsavel_{data_inicial_pv.strftime('%Y%m%d')}_{data_final_pv.strftime('%Y%m%d')}.xlsx",
                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
                
                
                st.dataframe(styled_pv_resp, hide_index=True, use_container_width=True)
        except Exception as e:
            st.error(f"Erro ao carregar totais por responsável: {e}")
    
        # # --- Indicador: Pendentes por Tipo de Evento x Responsável ---
        # query_pv_pivot = f"""
        # SELECT 
        #     cet.DESC_TIPO_EVENTO,
        #     eu.NOME_COMPLETO AS responsavel,
        #     COUNT(CASE WHEN oa.DATA_AGENDADA IS NULL THEN 1 END) AS total_pendente
        # FROM CRM_EVENTOS ce 
        # LEFT JOIN CRM_EVENTOS_TIPO cet ON 1=1
        #     AND cet.COD_TIPO_EVENTO = ce.COD_TIPO_EVENTO
        # LEFT JOIN EMPRESAS_USUARIOS eu ON 1=1
        #     AND eu.NOME = ce.RESPONSAVEL_PELO_EVENTO
        # LEFT JOIN OS_AGENDA oa ON 1=1
        #     AND ce.COD_EMPRESA = oa.CRM_COD_EMPRESA 
        #     AND ce.COD_EVENTO = oa.CRM_COD_EVENTO 
        # LEFT JOIN os os ON 1=1
        #     AND os.NUMERO_OS = oa.NUMERO_OS 
        #     AND os.COD_EMPRESA = oa.COD_EMPRESA 
        # WHERE 1=1
        # AND ce.COD_TIPO_EVENTO NOT IN (831,819,30,829,267,180,22,785,807,815,817,810,690)  
        # {filtro_empresa_pv}
        # AND TRUNC(
        #         CASE
        #             WHEN ce.data_novo_contato IS NULL
        #             THEN ce.data_evento
        #             ELSE ce.data_novo_contato
        #         END
        #         ) >= TO_DATE('{data_inicial_pv}', 'YYYY-MM-DD')
        # AND TRUNC(
        #         CASE
        #             WHEN ce.data_novo_contato IS NULL
        #             THEN ce.data_evento
        #             ELSE ce.data_novo_contato
        #         END
        #         ) <= TO_DATE('{data_final_pv}', 'YYYY-MM-DD')
        # AND ce.DATA_ENCERRAMENTO IS null
        # GROUP BY cet.DESC_TIPO_EVENTO, eu.NOME_COMPLETO
        # ORDER BY 1, 2
        # """
        # try:
        #     conn_pv3, cur_pv3 = oracle()
        #     cur_pv3.execute(query_pv_pivot)
        #     result_pv3 = cur_pv3.fetchall()
        #     columns_pv3 = [desc[0] for desc in cur_pv3.description]
        #     df_pv_pivot = pd.DataFrame(result_pv3, columns=columns_pv3)
        #     cur_pv3.close()
        #     conn_pv3.close()
    
        #     if not df_pv_pivot.empty:
        #         df_pv_pivot['TOTAL_PENDENTE'] = df_pv_pivot['TOTAL_PENDENTE'].astype(int)
        #         pivot = df_pv_pivot.pivot_table(
        #             index='DESC_TIPO_EVENTO',
        #             columns='RESPONSAVEL',
        #             values='TOTAL_PENDENTE',
        #             aggfunc='sum',
        #             fill_value=0
        #         )
        #         pivot.columns.name = None
        #         pivot.index.name = None
        #         pivot = pivot.loc[:, (pivot != 0).any(axis=0)]
        #         pivot['Total'] = pivot.sum(axis=1)
        #         total_row_pivot = pivot.sum(axis=0).rename('Total')
        #         pivot = pd.concat([pivot, total_row_pivot.to_frame().T])
        #         pivot = pivot.reset_index().rename(columns={'index': 'Tipo de Evento'})
    
        #         st.subheader("Pendentes por Tipo de Evento × Responsável")
        #         st.dataframe(pivot, hide_index=True, use_container_width=True)
        # except Exception as e:
        #     st.error(f"Erro ao carregar matriz de pendentes: {e}")
    
        # # --- Indicador: Agendamento Confirmado (com OS) por Tipo de Evento x Responsável ---
        # query_pv_os = f"""
        # SELECT 
        #     cet.DESC_TIPO_EVENTO,
        #     eu.NOME_COMPLETO AS responsavel,
        #     COUNT(CASE WHEN os.NUMERO_OS IS NOT NULL THEN 1 END) AS total_com_os
        # FROM CRM_EVENTOS ce 
        # LEFT JOIN CRM_EVENTOS_TIPO cet ON 1=1
        #     AND cet.COD_TIPO_EVENTO = ce.COD_TIPO_EVENTO
        # LEFT JOIN EMPRESAS_USUARIOS eu ON 1=1
        #     AND eu.NOME = ce.RESPONSAVEL_PELO_EVENTO
        # LEFT JOIN OS_AGENDA oa ON 1=1
        #     AND ce.COD_EMPRESA = oa.CRM_COD_EMPRESA 
        #     AND ce.COD_EVENTO = oa.CRM_COD_EVENTO 
        # LEFT JOIN os os ON 1=1
        #     AND os.NUMERO_OS = oa.NUMERO_OS 
        #     AND os.COD_EMPRESA = oa.COD_EMPRESA 
        # WHERE 1=1
        # AND ce.COD_TIPO_EVENTO NOT IN (831,819,30,829,267,180,22,785,807,815,817,810,690)  
        # {filtro_empresa_pv}
        # AND TRUNC(
        #         CASE
        #             WHEN ce.data_novo_contato IS NULL
        #             THEN ce.data_evento
        #             ELSE ce.data_novo_contato
        #         END
        #         ) >= TO_DATE('{data_inicial_pv}', 'YYYY-MM-DD')
        # AND TRUNC(
        #         CASE
        #             WHEN ce.data_novo_contato IS NULL
        #             THEN ce.data_evento
        #             ELSE ce.data_novo_contato
        #         END
        #         ) <= TO_DATE('{data_final_pv}', 'YYYY-MM-DD')
        # AND ce.DATA_ENCERRAMENTO IS null
        # GROUP BY cet.DESC_TIPO_EVENTO, eu.NOME_COMPLETO
        # ORDER BY 1, 2
        # """
        # try:
        #     conn_pv4, cur_pv4 = oracle()
        #     cur_pv4.execute(query_pv_os)
        #     result_pv4 = cur_pv4.fetchall()
        #     columns_pv4 = [desc[0] for desc in cur_pv4.description]
        #     df_pv_os = pd.DataFrame(result_pv4, columns=columns_pv4)
        #     cur_pv4.close()
        #     conn_pv4.close()
    
        #     if not df_pv_os.empty:
        #         df_pv_os['TOTAL_COM_OS'] = df_pv_os['TOTAL_COM_OS'].astype(int)
        #         pivot_os = df_pv_os.pivot_table(
        #             index='DESC_TIPO_EVENTO',
        #             columns='RESPONSAVEL',
        #             values='TOTAL_COM_OS',
        #             aggfunc='sum',
        #             fill_value=0
        #         )
        #         pivot_os.columns.name = None
        #         pivot_os.index.name = None
        #         pivot_os = pivot_os.loc[:, (pivot_os != 0).any(axis=0)]
        #         pivot_os['Total'] = pivot_os.sum(axis=1)
        #         total_row_os = pivot_os.sum(axis=0).rename('Total')
        #         pivot_os = pd.concat([pivot_os, total_row_os.to_frame().T])
        #         pivot_os = pivot_os.reset_index().rename(columns={'index': 'Tipo de Evento'})
    
        #         st.subheader("Agendamento Confirmado por Tipo de Evento × Responsável")
        #         st.dataframe(pivot_os, hide_index=True, use_container_width=True)
        # except Exception as e:
        #     st.error(f"Erro ao carregar matriz de agendamentos confirmados: {e}")
    
        # --- Indicador: Eventos Descartados ---
        query_pv_descartados = f"""
        SELECT 
            cd.descricao_descarte AS DESC_MOTIVO, 
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
        LEFT JOIN crm_descartes cd ON 1=1
            AND cd.cod_descarte = ce.cod_descarte 
        WHERE 1=1
        AND ce.COD_EMPRESA IN (11,33)
        AND ce.COD_TIPO_EVENTO IN (8,
            755,
            789,
            446,
            776,
            715,
            448,
            429,
            430,
            431,
            753,
            772,
            774,
            717,
            719,
            721,
            723,
            725,
            727,
            769,
            778,
            780)  
            and ce.status in ('D')
            AND TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) >= TO_DATE('{data_inicial_pv}', 'YYYY-MM-DD' )
            AND TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) <= TO_DATE('{data_final_pv}', 'YYYY-MM-DD' )
        
        GROUP BY cd.descricao_descarte  
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

                df_detalhamento_descartados = df_pv_desc_com_total.rename(columns={
                    'DESC_MOTIVO': 'Motivo',
                    'TOTAL_PENDENTE': 'Pendente',
                    'TOTAL_AGENDADO': 'Agendado',
                    'TOTAL': 'Total'
                }).copy()
    
                st.subheader("Eventos Descartados")
                st.dataframe(styled_pv_desc, hide_index=True, use_container_width=True)
        except Exception as e:
            st.error(f"Erro ao carregar eventos descartados: {e}")
    
        # --- Indicador: Descartes por Motivo x Responsável ---
        query_pv_desc_pivot = f"""
        SELECT 
            cd.descricao_descarte,
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
        LEFT JOIN crm_descartes cd ON 1=1
            AND cd.cod_descarte = ce.cod_descarte 
        WHERE 1=1
        AND ce.COD_EMPRESA IN (11,33)
        AND ce.COD_TIPO_EVENTO IN (8,
            755,
            789,
            446,
            776,
            715,
            448,
            429,
            430,
            431,
            753,
            772,
            774,
            717,
            719,
            721,
            723,
            725,
            727,
            769,
            778,
            780)  
            and ce.status in ('D')
            AND TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) >= TO_DATE('{data_inicial_pv}', 'YYYY-MM-DD' )
            AND TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) <= TO_DATE('{data_final_pv}', 'YYYY-MM-DD' )
        GROUP BY cd.descricao_descarte, eu.NOME_COMPLETO
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
                    index='DESCRICAO_DESCARTE',
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

                query_pv_desc_export = f"""
                SELECT DISTINCT
                    ce.COD_EMPRESA AS cod_empresa,
                    ce.COD_EVENTO AS cod_evento,
                    eu.NOME_COMPLETO AS nome_responsavel,
                    ce.COD_MOTIVO_PERDA,
                    cet.DESC_TIPO_EVENTO AS nome_evento,
                    cd.DESCRICAO_DESCARTE AS motivo_descarte
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
                LEFT JOIN crm_descartes cd ON 1=1
                    AND cd.COD_DESCARTE = ce.COD_DESCARTE
                WHERE 1=1
                AND ce.COD_EMPRESA IN (11,33)
                AND ce.COD_TIPO_EVENTO IN (8,
            755,
            789,
            446,
            776,
            715,
            448,
            429,
            430,
            431,
            753,
            772,
            774,
            717,
            719,
            721,
            723,
            725,
            727,
            769,
            778,
            780)  
            and ce.status in ('D')
            AND TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) >= TO_DATE('{data_inicial_pv}', 'YYYY-MM-DD' )
            AND TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) <= TO_DATE('{data_final_pv}', 'YYYY-MM-DD' )
                ORDER BY 1, 2
                """
                try:
                    conn_pv_desc_export, cur_pv_desc_export = oracle()
                    cur_pv_desc_export.execute(query_pv_desc_export)
                    result_pv_desc_export = cur_pv_desc_export.fetchall()
                    columns_pv_desc_export = [desc[0] for desc in cur_pv_desc_export.description]
                    df_pv_desc_export = pd.DataFrame(result_pv_desc_export, columns=columns_pv_desc_export)
                    cur_pv_desc_export.close()
                    conn_pv_desc_export.close()

                    if not df_pv_desc_export.empty:
                        buffer_excel_pv_desc = io.BytesIO()
                        with pd.ExcelWriter(buffer_excel_pv_desc, engine='xlsxwriter') as writer:
                            df_pv_desc_export.to_excel(writer, index=False, sheet_name='Descartes')
                        buffer_excel_pv_desc.seek(0)

                        st.download_button(
                            label='Baixar Excel dos Descartes',
                            data=buffer_excel_pv_desc.getvalue(),
                            file_name=f"ciclo_veiculos_descartes_{data_inicial_pv.strftime('%Y%m%d')}_{data_final_pv.strftime('%Y%m%d')}.xlsx",
                            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                        )
                    else:
                        st.info("Nenhum descarte encontrado para exportação no período selecionado.")
                except Exception as e:
                    st.error(f"Erro ao gerar planilha de descartes: {e}")

                st.dataframe(styled_desc_piv, hide_index=True, use_container_width=True)
        except Exception as e:
            st.error(f"Erro ao carregar matriz de descartes: {e}")

        # --- Indicador: Eventos Perdidos ---
        query_pv_perdidos = f"""
        SELECT
            cmp.DESC_MOTIVO,
            COUNT(CASE WHEN oa.DATA_AGENDADA IS NULL THEN 1 END) AS total_pendente,
            COUNT(CASE WHEN oa.DATA_AGENDADA IS NOT NULL THEN 1 END) AS total_agendado,
            COUNT(*) AS total
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
        LEFT JOIN CRM_TIPO_FECHAMENTO ctf ON 1=1
            AND ctf.COD_TIPO_FECHAMENTO = ce.COD_TIPO_FECHAMENTO
        WHERE 1=1
        AND ce.COD_EMPRESA IN (11,33)
        AND ce.COD_TIPO_EVENTO IN (8,
            755,
            789,
            446,
            776,
            715,
            448,
            429,
            430,
            431,
            753,
            772,
            774,
            717,
            719,
            721,
            723,
            725,
            727,
            769,
            778,
            780)  
        AND ce.STATUS = 'E'
        AND ctf.COD_TIPO_FECHAMENTO IN (0,2)
        AND TRUNC(ce.DATA_ENCERRAMENTO) >= TO_DATE('{data_inicial_pv}', 'YYYY-MM-DD')
        AND TRUNC(ce.DATA_ENCERRAMENTO) <= TO_DATE('{data_final_pv}', 'YYYY-MM-DD')
        GROUP BY cmp.DESC_MOTIVO
        ORDER BY 1
        """
        try:
            conn_pv8, cur_pv8 = oracle()
            cur_pv8.execute(query_pv_perdidos)
            result_pv8 = cur_pv8.fetchall()
            columns_pv8 = [desc[0] for desc in cur_pv8.description]
            df_pv_perdidos = pd.DataFrame(result_pv8, columns=columns_pv8)
            cur_pv8.close()
            conn_pv8.close()

            if not df_pv_perdidos.empty:
                df_pv_perdidos['TOTAL_PENDENTE'] = df_pv_perdidos['TOTAL_PENDENTE'].astype(int)
                df_pv_perdidos['TOTAL_AGENDADO'] = df_pv_perdidos['TOTAL_AGENDADO'].astype(int)
                df_pv_perdidos['TOTAL'] = df_pv_perdidos['TOTAL'].astype(int)

                total_row_perdidos = pd.DataFrame({
                    'DESC_MOTIVO': ['Total'],
                    'TOTAL_PENDENTE': [df_pv_perdidos['TOTAL_PENDENTE'].sum()],
                    'TOTAL_AGENDADO': [df_pv_perdidos['TOTAL_AGENDADO'].sum()],
                    'TOTAL': [df_pv_perdidos['TOTAL'].sum()]
                })
                df_pv_perdidos_com_total = pd.concat([df_pv_perdidos, total_row_perdidos], ignore_index=True)

                styled_pv_perdidos = df_pv_perdidos_com_total.rename(columns={
                    'DESC_MOTIVO': 'Motivo da Perda',
                    'TOTAL_PENDENTE': 'Pendente',
                    'TOTAL_AGENDADO': 'Agendado',
                    'TOTAL': 'Total'
                }).style.apply(
                    lambda x: ['font-weight: bold' if x.name == len(df_pv_perdidos_com_total) - 1 else '' for _ in x], axis=1
                )

                df_detalhamento_encerrados = df_pv_perdidos_com_total.rename(columns={
                    'DESC_MOTIVO': 'Motivo da Perda',
                    'TOTAL_PENDENTE': 'Pendente',
                    'TOTAL_AGENDADO': 'Agendado',
                    'TOTAL': 'Total'
                }).copy()

                st.subheader("Eventos Perdidos")
                st.dataframe(styled_pv_perdidos, hide_index=True, use_container_width=True)
        except Exception as e:
            st.error(f"Erro ao carregar eventos perdidos: {e}")

        # --- Indicador: Perdas por Motivo x Responsável ---
        query_pv_perdidos_pivot = f"""
        SELECT
            cmp.DESC_MOTIVO,
            eu.NOME_COMPLETO AS responsavel,
            COUNT(*) AS total
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
        LEFT JOIN CRM_TIPO_FECHAMENTO ctf ON 1=1
            AND ctf.COD_TIPO_FECHAMENTO = ce.COD_TIPO_FECHAMENTO
        WHERE 1=1
        AND ce.COD_EMPRESA IN (11,33)
        AND ce.COD_TIPO_EVENTO IN (8,
            755,
            789,
            446,
            776,
            715,
            448,
            429,
            430,
            431,
            753,
            772,
            774,
            717,
            719,
            721,
            723,
            725,
            727,
            769,
            778,
            780)  
        AND ce.STATUS = 'E'
        AND ctf.COD_TIPO_FECHAMENTO IN (0,2)
        AND TRUNC(ce.DATA_ENCERRAMENTO) >= TO_DATE('{data_inicial_pv}', 'YYYY-MM-DD')
        AND TRUNC(ce.DATA_ENCERRAMENTO) <= TO_DATE('{data_final_pv}', 'YYYY-MM-DD')
        GROUP BY cmp.DESC_MOTIVO, eu.NOME_COMPLETO
        ORDER BY 1, 2
        """
        try:
            conn_pv9, cur_pv9 = oracle()
            cur_pv9.execute(query_pv_perdidos_pivot)
            result_pv9 = cur_pv9.fetchall()
            columns_pv9 = [desc[0] for desc in cur_pv9.description]
            df_pv_perdidos_piv = pd.DataFrame(result_pv9, columns=columns_pv9)
            cur_pv9.close()
            conn_pv9.close()

            if not df_pv_perdidos_piv.empty:
                df_pv_perdidos_piv['TOTAL'] = df_pv_perdidos_piv['TOTAL'].astype(int)
                pivot_perdidos = df_pv_perdidos_piv.pivot_table(
                    index='DESC_MOTIVO',
                    columns='RESPONSAVEL',
                    values='TOTAL',
                    aggfunc='sum',
                    fill_value=0
                )
                pivot_perdidos.columns.name = None
                pivot_perdidos.index.name = None
                pivot_perdidos = pivot_perdidos.loc[:, (pivot_perdidos != 0).any(axis=0)]
                pivot_perdidos['Total'] = pivot_perdidos.sum(axis=1)
                total_row_perdidos_piv = pivot_perdidos.sum(axis=0).rename('Total')
                pivot_perdidos = pd.concat([pivot_perdidos, total_row_perdidos_piv.to_frame().T])
                pivot_perdidos = pivot_perdidos.reset_index().rename(columns={'index': 'Motivo'})

                styled_perdidos_piv = pivot_perdidos.style.apply(
                    lambda x: ['font-weight: bold' if x.name == len(pivot_perdidos) - 1 else '' for _ in x], axis=1
                )

                st.subheader("Perdas por Motivo × Responsável")

                query_pv_perdidos_export = f"""
                SELECT DISTINCT
                    ce.COD_EMPRESA AS cod_empresa,
                    ce.COD_EVENTO AS cod_evento,
                    eu.NOME_COMPLETO AS nome_responsavel,
                    ce.COD_MOTIVO_PERDA,
                    cet.DESC_TIPO_EVENTO AS nome_evento,
                    cmp.DESC_MOTIVO AS motivo_perda
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
                LEFT JOIN CRM_TIPO_FECHAMENTO ctf ON 1=1
                    AND ctf.COD_TIPO_FECHAMENTO = ce.COD_TIPO_FECHAMENTO
                WHERE 1=1
                AND ce.COD_EMPRESA IN (11,33)
                AND ce.COD_TIPO_EVENTO IN (8,
            755,
            789,
            446,
            776,
            715,
            448,
            429,
            430,
            431,
            753,
            772,
            774,
            717,
            719,
            721,
            723,
            725,
            727,
            769,
            778,
            780)  
        AND ce.STATUS = 'E'
        AND ctf.COD_TIPO_FECHAMENTO IN (0,2)
        AND TRUNC(ce.DATA_ENCERRAMENTO) >= TO_DATE('{data_inicial_pv}', 'YYYY-MM-DD')
        AND TRUNC(ce.DATA_ENCERRAMENTO) <= TO_DATE('{data_final_pv}', 'YYYY-MM-DD')
                ORDER BY 1, 2
                """
                try:
                    conn_pv_perdidos_exp, cur_pv_perdidos_exp = oracle()
                    cur_pv_perdidos_exp.execute(query_pv_perdidos_export)
                    result_pv_perdidos_exp = cur_pv_perdidos_exp.fetchall()
                    columns_pv_perdidos_exp = [desc[0] for desc in cur_pv_perdidos_exp.description]
                    df_pv_perdidos_exp = pd.DataFrame(result_pv_perdidos_exp, columns=columns_pv_perdidos_exp)
                    cur_pv_perdidos_exp.close()
                    conn_pv_perdidos_exp.close()

                    if not df_pv_perdidos_exp.empty:
                        buffer_excel_pv_perdidos = io.BytesIO()
                        with pd.ExcelWriter(buffer_excel_pv_perdidos, engine='xlsxwriter') as writer:
                            df_pv_perdidos_exp.to_excel(writer, index=False, sheet_name='Eventos Perdidos')
                        buffer_excel_pv_perdidos.seek(0)

                        st.download_button(
                            label='Baixar Excel dos Perdidos',
                            data=buffer_excel_pv_perdidos.getvalue(),
                            file_name=f"ciclo_veiculos_perdidos_{data_inicial_pv.strftime('%Y%m%d')}_{data_final_pv.strftime('%Y%m%d')}.xlsx",
                            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                        )
                    else:
                        st.info("Nenhum evento perdido encontrado para exportação no período selecionado.")
                except Exception as e:
                    st.error(f"Erro ao gerar planilha de eventos perdidos: {e}")

                st.dataframe(styled_perdidos_piv, hide_index=True, use_container_width=True)
        except Exception as e:
            st.error(f"Erro ao carregar matriz de eventos perdidos: {e}")
    
        st.subheader("Detalhamento")
        try:
            query_detalhamento_abertos = f"""
            SELECT DISTINCT
                TO_CHAR(ce.COD_EMPRESA) || TO_CHAR(ce.COD_EVENTO) AS evento,
                ce.VEIC_CHASSI_COMPLETO AS chassi_completo,
                ce.COD_EMPRESA AS cod_empres,
                ce.COD_EVENTO AS cod_evento,
                CASE WHEN ce.COD_CLIENTE = 1 THEN ce.NOME_CLIENTE_AVULSO ELSE c.NOME END AS nome_cliente,
                cet.DESC_TIPO_EVENTO AS tipo_evento,
                TRUNC(CASE WHEN ce.DATA_NOVO_CONTATO IS NULL THEN ce.DATA_EVENTO ELSE ce.DATA_NOVO_CONTATO END) AS data_contato,
                eu.NOME_COMPLETO AS responsavel,
                ca.ANDAMENTO AS andamento,
                NULL AS motivo_descarte,
                NULL AS motivo_perda,
                s.COD_OS_AGENDA AS cod_agenda,
                s.DATA_COMECA AS data_agendamento,
                o.NUMERO_OS AS numero_os
            FROM CRM_EVENTOS ce
            LEFT JOIN CRM_EVENTOS_TIPO cet ON 1=1
                AND cet.COD_TIPO_EVENTO = ce.COD_TIPO_EVENTO
            LEFT JOIN EMPRESAS_USUARIOS eu ON 1=1
                AND eu.NOME = ce.RESPONSAVEL_PELO_EVENTO
            LEFT JOIN CRM_ANDAMENTO ca ON 1=1
                AND ca.COD_ANDAMENTO = ce.COD_ANDAMENTO
            LEFT JOIN clientes c ON ce.COD_CLIENTE = c.COD_CLIENTE
            LEFT JOIN os_agenda_servicos s ON 1=1
                AND ce.COD_EMPRESA = s.CRM_COD_EMPRESA
                AND ce.COD_EVENTO = s.CRM_COD_EVENTO
            LEFT JOIN os o ON 1=1
                AND s.COD_EMPRESA = o.COD_EMPRESA
                AND s.COD_OS_AGENDA = o.COD_OS_AGENDA
                AND o.ORCAMENTO <> 'S'
            WHERE 1=1
            AND ce.COD_EMPRESA IN (11,33)
            AND ce.COD_TIPO_EVENTO IN (8,755,789,446,776,715,448,429,430,431,753,772,774,717,719,721,723,725,727,769,778,780)
            {filtro_empresa_pv}
            AND ce.STATUS IN ('P','A')
            AND TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) <= TO_DATE('{now_str}', 'YYYY-MM-DD')
            ORDER BY 1, 2
            """

            query_detalhamento_encerrados = f"""
            SELECT DISTINCT
                TO_CHAR(ce.COD_EMPRESA) || TO_CHAR(ce.COD_EVENTO) AS evento,
                ce.VEIC_CHASSI_COMPLETO AS chassi_completo,
                ce.COD_EMPRESA AS cod_empres,
                ce.COD_EVENTO AS cod_evento,
                CASE WHEN ce.COD_CLIENTE = 1 THEN ce.NOME_CLIENTE_AVULSO ELSE c.NOME END AS nome_cliente,
                cet.DESC_TIPO_EVENTO AS tipo_evento,
                TRUNC(CASE WHEN ce.DATA_NOVO_CONTATO IS NULL THEN ce.DATA_EVENTO ELSE ce.DATA_NOVO_CONTATO END) AS data_contato,
                eu.NOME_COMPLETO AS responsavel,
                ca.ANDAMENTO AS andamento,
                NULL AS motivo_descarte,
                cmp.DESC_MOTIVO AS motivo_perda,
                s.COD_OS_AGENDA AS cod_agenda,
                s.DATA_COMECA AS data_agendamento,
                o.NUMERO_OS AS numero_os
            FROM CRM_EVENTOS ce
            LEFT JOIN CRM_EVENTOS_TIPO cet ON 1=1
                AND cet.COD_TIPO_EVENTO = ce.COD_TIPO_EVENTO
            LEFT JOIN EMPRESAS_USUARIOS eu ON 1=1
                AND eu.NOME = ce.RESPONSAVEL_PELO_EVENTO
            LEFT JOIN CRM_ANDAMENTO ca ON 1=1
                AND ca.COD_ANDAMENTO = ce.COD_ANDAMENTO
            LEFT JOIN clientes c ON ce.COD_CLIENTE = c.COD_CLIENTE
            LEFT JOIN CRM_MOTIVO_PERDAS cmp ON 1=1
                AND cmp.COD_MOTIVO_PERDA = ce.COD_MOTIVO_PERDA
            LEFT JOIN CRM_TIPO_FECHAMENTO ctf ON 1=1
                AND ctf.COD_TIPO_FECHAMENTO = ce.COD_TIPO_FECHAMENTO
            LEFT JOIN os_agenda_servicos s ON 1=1
                AND ce.COD_EMPRESA = s.CRM_COD_EMPRESA
                AND ce.COD_EVENTO = s.CRM_COD_EVENTO
            LEFT JOIN os o ON 1=1
                AND s.COD_EMPRESA = o.COD_EMPRESA
                AND s.COD_OS_AGENDA = o.COD_OS_AGENDA
                AND o.ORCAMENTO <> 'S'
            WHERE 1=1
            AND ce.COD_EMPRESA IN (11,33)
            AND ce.COD_TIPO_EVENTO IN (8,755,789,446,776,715,448,429,430,431,753,772,774,717,719,721,723,725,727,769,778,780)
            {filtro_empresa_pv}
            AND ce.STATUS = 'E'
            AND ctf.COD_TIPO_FECHAMENTO IN (0,2)
            AND TRUNC(ce.DATA_ENCERRAMENTO) >= TO_DATE('{data_inicial_pv}', 'YYYY-MM-DD')
            AND TRUNC(ce.DATA_ENCERRAMENTO) <= TO_DATE('{data_final_pv}', 'YYYY-MM-DD')
            ORDER BY 1, 2
            """

            query_detalhamento_descartados = f"""
            SELECT DISTINCT
                TO_CHAR(ce.COD_EMPRESA) || TO_CHAR(ce.COD_EVENTO) AS evento,
                ce.VEIC_CHASSI_COMPLETO AS chassi_completo,
                ce.COD_EMPRESA AS cod_empres,
                ce.COD_EVENTO AS cod_evento,
                CASE WHEN ce.COD_CLIENTE = 1 THEN ce.NOME_CLIENTE_AVULSO ELSE c.NOME END AS nome_cliente,
                cet.DESC_TIPO_EVENTO AS tipo_evento,
                TRUNC(CASE WHEN ce.DATA_NOVO_CONTATO IS NULL THEN ce.DATA_EVENTO ELSE ce.DATA_NOVO_CONTATO END) AS data_contato,
                eu.NOME_COMPLETO AS responsavel,
                ca.ANDAMENTO AS andamento,
                cd.DESCRICAO_DESCARTE AS motivo_descarte,
                NULL AS motivo_perda,
                s.COD_OS_AGENDA AS cod_agenda,
                s.DATA_COMECA AS data_agendamento,
                o.NUMERO_OS AS numero_os
            FROM CRM_EVENTOS ce
            LEFT JOIN CRM_EVENTOS_TIPO cet ON 1=1
                AND cet.COD_TIPO_EVENTO = ce.COD_TIPO_EVENTO
            LEFT JOIN EMPRESAS_USUARIOS eu ON 1=1
                AND eu.NOME = ce.RESPONSAVEL_PELO_EVENTO
            LEFT JOIN CRM_ANDAMENTO ca ON 1=1
                AND ca.COD_ANDAMENTO = ce.COD_ANDAMENTO
            LEFT JOIN clientes c ON ce.COD_CLIENTE = c.COD_CLIENTE
            LEFT JOIN crm_descartes cd ON 1=1
                AND cd.COD_DESCARTE = ce.COD_DESCARTE
            LEFT JOIN os_agenda_servicos s ON 1=1
                AND ce.COD_EMPRESA = s.CRM_COD_EMPRESA
                AND ce.COD_EVENTO = s.CRM_COD_EVENTO
            LEFT JOIN os o ON 1=1
                AND s.COD_EMPRESA = o.COD_EMPRESA
                AND s.COD_OS_AGENDA = o.COD_OS_AGENDA
                AND o.ORCAMENTO <> 'S'
            WHERE 1=1
            AND ce.COD_EMPRESA IN (11,33)
            AND ce.COD_TIPO_EVENTO IN (8,755,789,446,776,715,448,429,430,431,753,772,774,717,719,721,723,725,727,769,778,780)
            {filtro_empresa_pv}
            AND ce.STATUS IN ('D')
            AND TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) >= TO_DATE('{data_inicial_pv}', 'YYYY-MM-DD')
            AND TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) <= TO_DATE('{data_final_pv}', 'YYYY-MM-DD')
            ORDER BY 1, 2
            """

            conn_det, cur_det = oracle()

            cur_det.execute(query_detalhamento_abertos)
            df_detalhamento_abertos = pd.DataFrame(cur_det.fetchall(), columns=[desc[0] for desc in cur_det.description])

            cur_det.execute(query_detalhamento_encerrados)
            df_detalhamento_encerrados = pd.DataFrame(cur_det.fetchall(), columns=[desc[0] for desc in cur_det.description])

            cur_det.execute(query_detalhamento_descartados)
            df_detalhamento_descartados = pd.DataFrame(cur_det.fetchall(), columns=[desc[0] for desc in cur_det.description])

            cur_det.close()
            conn_det.close()

            for df_det in [df_detalhamento_abertos, df_detalhamento_encerrados, df_detalhamento_descartados]:
                if not df_det.empty and 'DATA_CONTATO' in df_det.columns:
                    df_det['DATA_CONTATO'] = pd.to_datetime(df_det['DATA_CONTATO'], errors='coerce').dt.strftime('%d/%m/%Y').fillna('-')
                if not df_det.empty and 'DATA_AGENDAMENTO' in df_det.columns:
                    df_det['DATA_AGENDAMENTO'] = pd.to_datetime(df_det['DATA_AGENDAMENTO'], errors='coerce').dt.strftime('%d/%m/%Y').fillna('-')

            buffer_detalhamento = io.BytesIO()
            with pd.ExcelWriter(buffer_detalhamento, engine='xlsxwriter') as writer:
                (df_detalhamento_abertos if not df_detalhamento_abertos.empty else pd.DataFrame({'info': ['Sem dados no período']})).to_excel(
                    writer,
                    index=False,
                    sheet_name='Eventos abertos'
                )
                (df_detalhamento_encerrados if not df_detalhamento_encerrados.empty else pd.DataFrame({'info': ['Sem dados no período']})).to_excel(
                    writer,
                    index=False,
                    sheet_name='Eventos Encerrados'
                )
                (df_detalhamento_descartados if not df_detalhamento_descartados.empty else pd.DataFrame({'info': ['Sem dados no período']})).to_excel(
                    writer,
                    index=False,
                    sheet_name='Eventos Descartados'
                )
            buffer_detalhamento.seek(0)

            st.download_button(
                label='Baixar Detalhamento.xlsx',
                data=buffer_detalhamento.getvalue(),
                file_name='Detalhamento.xlsx',
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        except Exception as e:
            st.error(f"Erro ao gerar Detalhamento.xlsx: {e}")
    
    except Exception as e:
        st.error(f"Erro ao executar a consulta: {e}")
    