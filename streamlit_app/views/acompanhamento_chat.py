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

EMAILS_ACOMPANHAMENTO_CHAT = [
    "pablo.ti@caiuas.com.br",
]


def render():
    st.title("Acompanhamento Chat (Chatwoot)")
    
    query_acomp_chat = """
    SELECT 
        COALESCE(u.name, 'Sem Responsável (Fila)') AS nome_usuario,
        COUNT(CASE 
            WHEN c.status IN (0, 2) AND c.waiting_since IS NOT NULL 
            THEN 1 
        END) AS qtd_pendentes,
        COUNT(CASE 
            WHEN c.status = 3 
            THEN 1 
        END) AS qtd_adiados,
        COUNT(CASE 
            WHEN c.status IN (0, 2) 
                 AND c.waiting_since < (NOW() - INTERVAL '2 hours') 
            THEN 1 
        END) AS qtd_atrasados
    FROM conversations c
    LEFT JOIN users u ON c.assignee_id = u.id
    WHERE c.status IN (0, 2, 3)
    GROUP BY 
        u.id, 
        u.name
    HAVING 
        COUNT(CASE WHEN c.status IN (0, 2) AND c.waiting_since IS NOT NULL THEN 1 END) > 0 OR
        COUNT(CASE WHEN c.status = 3 THEN 1 END) > 0 OR
        COUNT(CASE WHEN c.status IN (0, 2) AND c.waiting_since < (NOW() - INTERVAL '2 hours') THEN 1 END) > 0
    ORDER BY 
        qtd_atrasados DESC, 
        qtd_pendentes DESC
    """
    
    try:
        conn_ac, cur_ac = chatwoot()
        cur_ac.execute(query_acomp_chat)
        result_ac = cur_ac.fetchall()
        columns_ac = [desc[0] for desc in cur_ac.description]
        df_ac = pd.DataFrame(result_ac, columns=columns_ac)
        cur_ac.close()
        conn_ac.close()
    
        df_ac['qtd_pendentes'] = df_ac['qtd_pendentes'].astype(int)
        df_ac['qtd_adiados'] = df_ac['qtd_adiados'].astype(int)
        df_ac['qtd_atrasados'] = df_ac['qtd_atrasados'].astype(int)
    
        total_row = pd.DataFrame({
            'nome_usuario': ['Total'],
            'qtd_pendentes': [df_ac['qtd_pendentes'].sum()],
            'qtd_adiados': [df_ac['qtd_adiados'].sum()],
            'qtd_atrasados': [df_ac['qtd_atrasados'].sum()],
        })
        df_ac_com_total = pd.concat([df_ac, total_row], ignore_index=True)
    
        styled_ac = df_ac_com_total.rename(columns={
            'nome_usuario': 'Responsável',
            'qtd_pendentes': 'Pendentes',
            'qtd_adiados': 'Adiados',
            'qtd_atrasados': 'Atrasados (> 2h)',
        }).style.apply(
            lambda x: ['font-weight: bold' if x.name == len(df_ac_com_total) - 1 else '' for _ in x], axis=1
        ).applymap(
            lambda v: 'color: red; font-weight: bold' if isinstance(v, int) and v > 0 else '',
            subset=['Atrasados (> 2h)']
        )
    
        st.subheader("Conversas abertas por responsável")
        st.dataframe(styled_ac, hide_index=True, use_container_width=True)
    
    except Exception as e:
        st.error(f"Erro ao carregar dados do Chatwoot: {e}")
    
    # Tabela detalhada
    try:
        query_detalhe = """
        SELECT
            c.id AS conversation_id,
            c.account_id,
            COALESCE(u.name, 'Sem Responsável (Fila)') AS responsavel,
            c.created_at AT TIME ZONE 'UTC' AT TIME ZONE 'America/Sao_Paulo' AS data_inicio,
            EXTRACT(EPOCH FROM (NOW() - c.created_at AT TIME ZONE 'UTC')) / 60 AS minutos_aberto,
            c.status,
            (
                SELECT m.message_type
                FROM messages m
                WHERE m.conversation_id = c.id
                ORDER BY m.created_at DESC
                LIMIT 1
            ) AS ultimo_tipo_mensagem
        FROM conversations c
        LEFT JOIN users u ON c.assignee_id = u.id
        WHERE c.status IN (0, 2, 3)
        ORDER BY c.created_at ASC
        """
        conn_det, cur_det = chatwoot()
        cur_det.execute(query_detalhe)
        result_det = cur_det.fetchall()
        columns_det = [desc[0] for desc in cur_det.description]
        df_det = pd.DataFrame(result_det, columns=columns_det)
        cur_det.close()
        conn_det.close()
    
        df_det['link_chat'] = df_det.apply(
            lambda row: f"https://chat.caiuas.com.br/app/accounts/{row['account_id']}/conversations/{row['conversation_id']}"
            if str(row.get('account_id', '')).strip() != ''
            else '',
            axis=1
        )
    
        def fmt_tempo(minutos):
            if minutos is None:
                return ''
            h = int(minutos) // 60
            m = int(minutos) % 60
            return f"{h}h {m:02d}min"
    
        df_det['tempo_atendimento'] = df_det['minutos_aberto'].apply(fmt_tempo)
    
        status_map = {0: 'Aberto', 2: 'Pendente', 3: 'Adiado'}
        df_det['status_label'] = df_det['status'].map(status_map).fillna(df_det['status'].astype(str))
    
        # 1 = outgoing (agente), 0 = incoming (cliente)
        df_det['respondida'] = df_det['ultimo_tipo_mensagem'].apply(
            lambda v: '🟢' if v == 1 else '🔴'
        )
    
        st.subheader("Detalhamento das conversas")
        fcol_det1, fcol_det2 = st.columns(2)
        with fcol_det1:
            opcoes_resp_det = ['Todos'] + sorted(df_det['responsavel'].unique().tolist())
            filtro_resp_det = st.selectbox("Filtrar por responsável", opcoes_resp_det, key="ac_filtro_resp")
        with fcol_det2:
            filtro_status_det = st.selectbox("Filtrar por status", ['Todos', 'Aberto', 'Pendente', 'Adiado'], key="ac_filtro_status")
    
        df_det_filtrado = df_det.copy()
        if filtro_resp_det != 'Todos':
            df_det_filtrado = df_det_filtrado[df_det_filtrado['responsavel'] == filtro_resp_det]
        if filtro_status_det != 'Todos':
            df_det_filtrado = df_det_filtrado[df_det_filtrado['status_label'] == filtro_status_det]
    
        st.caption(f"{len(df_det_filtrado)} conversa(s)")
        st.dataframe(
            df_det_filtrado[['respondida', 'responsavel', 'status_label', 'data_inicio', 'tempo_atendimento', 'link_chat']].rename(columns={
                'respondida': 'Resp.',
                'responsavel': 'Responsável',
                'status_label': 'Status',
                'data_inicio': 'Início',
                'tempo_atendimento': 'Tempo Aberto',
                'link_chat': 'Link',
            }),
            hide_index=True,
            use_container_width=True,
            column_config={
                "Link": st.column_config.LinkColumn("Link", display_text="Abrir"),
                "Início": st.column_config.DatetimeColumn("Início", format="DD/MM/YYYY HH:mm"),
            }
        )
    except Exception as e:
        st.error(f"Erro ao carregar detalhamento: {e}")
    