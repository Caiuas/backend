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

EMAILS_CHAT = [
    "pablo.ti@caiuas.com.br",
    "cristiane.aguilar@caiuas.com.br",
    "marcelotcf@caiuas.com.br"
]


def render():
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
    