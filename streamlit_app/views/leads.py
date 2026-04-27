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

EMAILS_HAMADA = [
    "pablo.ti@caiuas.com.br",
    "cristiane.aguilar@caiuas.com.br",
    "marcelotcf@caiuas.com.br"
]


def render():
    st.title("Acompanhamento de Leads")
    data_inicial_hamada = st.sidebar.date_input("Data Inicial", datetime.now().date(), key="hamada_data_inicial")
    data_final_hamada = st.sidebar.date_input("Data Final", datetime.now().date(), key="hamada_data_final")
    query = f"""
    SELECT 
        ce.COD_EMPRESA, 
        ce.COD_EVENTO,
        to_char(ce.cod_proposta) as cod_proposta,
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
        to_date(ce.data_visita ) data_visita,
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
    