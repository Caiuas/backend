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

EMAILS_ACOMPANHAMENTO_DIARIO = [
    "welder@caiuas.com.br",
    "admilson@caiuas.com.br",
    "cristiane.aguilar@caiuas.com.br",
    "pablo.ti@caiuas.com.br",
    "marcelotcf@caiuas.com.br"
]


def render():
    st.title("Acompanhamento Diário")
    data_inicial_ad = st.sidebar.date_input("Data Inicial", datetime.now().date(), key="ad_data_inicial")
    data_final_ad = st.sidebar.date_input("Data Final", datetime.now().date(), key="ad_data_final")
    empresa_ad = st.sidebar.selectbox("Filtrar por empresa", ["Todas", "11", "33"], key="ad_empresa")
    filtro_empresa_ad = f"AND eu.cod_empresa = {empresa_ad}" if empresa_ad != "Todas" else ""
    
    from dateutil.relativedelta import relativedelta
    data_inicial_anterior = data_inicial_ad - relativedelta(months=1)
    data_final_anterior = data_final_ad - relativedelta(months=1)
    
    try:
        conn_oracle, cur_oracle = oracle()
        conn_chat, cur_chat = chatwoot()
        
        # Acompanhamento de eventos Por responsável
        query_responsaveis = f"""
        SELECT
            NVL(upper(eu.nome_completo), 'SEM RESPONSÁVEL') responsavel,
            COUNT(CASE 
                WHEN TRUNC(NVL(ce.data_novo_contato, ce.data_evento)) < TRUNC(SYSDATE) 
                THEN 1 
            END) AS ATRASADO,
            COUNT(CASE 
                WHEN TRUNC(NVL(ce.data_novo_contato, ce.data_evento)) = TRUNC(SYSDATE) 
                THEN 1 
            END) AS HOJE,
            COUNT(CASE 
                WHEN TRUNC(NVL(ce.data_novo_contato, ce.data_evento)) > TRUNC(SYSDATE) 
                THEN 1 
            END) AS FUTURO
        FROM
            CRM_EVENTOS ce
        LEFT JOIN EMPRESAS_USUARIOS eu ON
            eu.nome = ce.RESPONSAVEL_PELO_EVENTO
        LEFT JOIN CRM_ANDAMENTO ca ON
            ca.COD_ANDAMENTO = ce.COD_ANDAMENTO
        LEFT JOIN MIDIA m ON
            m.COD_MIDIA = ce.COD_MIDIA 
        LEFT JOIN clientes c ON
            ce.COD_CLIENTE = c.COD_CLIENTE
        LEFT JOIN CRM_EVENTOS_TIPO cet ON 
            cet.COD_TIPO_EVENTO = ce.COD_TIPO_EVENTO
        LEFT JOIN CRM_DESCARTES cd ON 
            cd.COD_DESCARTE = ce.COD_DESCARTE
        LEFT JOIN CRM_MOTIVO_PERDAS cmp ON 
            cmp.cod_motivo_perda = ce.cod_motivo_perda
        LEFT JOIN produtos_modelos pm ON 
            pm.COD_PRODUTO = ce.COD_PRODUTO AND pm.COD_MODELO = ce.COD_MODELO
        LEFT JOIN caiuas_crm_eventos_descartados ced ON 
            ced.cod_empresa = ce.COD_EMPRESA AND ced.cod_evento = ce.COD_EVENTO
        WHERE
            ce.cod_tipo_evento IN (
                '829','831','795','793','797','799','819','821','785','807','815','817','810','812'
            )
            AND ce.status IN ('P')
        GROUP BY
            eu.nome_completo
        ORDER BY 3 desc
        """
        cur_oracle.execute(query_responsaveis)
        dados_responsaveis = cur_oracle.fetchall()
        df_responsaveis = pd.DataFrame(dados_responsaveis, columns=[desc[0] for desc in cur_oracle.description])
        
        st.subheader("Acompanhamento de eventos Por responsável")
        st.dataframe(df_responsaveis, hide_index=True)
        
        # Acompanhamento de eventos Por Empresa
        query_empresas = f"""
        SELECT
            CASE 
                WHEN eu.cod_empresa = 11 THEN 'Sorocaba'
                WHEN eu.cod_empresa = 33 THEN 'Indaiatuba'
                WHEN eu.cod_empresa = 111 THEN 'LLA'
                ELSE NVL(to_char(eu.cod_empresa), 'SEM EMPRESA')
            END AS empresa,
            COUNT(CASE 
                WHEN TRUNC(NVL(ce.data_novo_contato, ce.data_evento)) < TRUNC(SYSDATE) 
                THEN 1 
            END) AS ATRASADO,
            COUNT(CASE 
                WHEN TRUNC(NVL(ce.data_novo_contato, ce.data_evento)) = TRUNC(SYSDATE) 
                THEN 1 
            END) AS HOJE,
            COUNT(CASE 
                WHEN TRUNC(NVL(ce.data_novo_contato, ce.data_evento)) > TRUNC(SYSDATE) 
                THEN 1 
            END) AS FUTURO
        FROM
            CRM_EVENTOS ce
        LEFT JOIN EMPRESAS_USUARIOS eu ON
            eu.nome = ce.RESPONSAVEL_PELO_EVENTO
        LEFT JOIN CRM_ANDAMENTO ca ON
            ca.COD_ANDAMENTO = ce.COD_ANDAMENTO
        LEFT JOIN MIDIA m ON
            m.COD_MIDIA = ce.COD_MIDIA 
        LEFT JOIN clientes c ON
            ce.COD_CLIENTE = c.COD_CLIENTE
        LEFT JOIN CRM_EVENTOS_TIPO cet ON 
            cet.COD_TIPO_EVENTO = ce.COD_TIPO_EVENTO
        LEFT JOIN CRM_DESCARTES cd ON 
            cd.COD_DESCARTE = ce.COD_DESCARTE
        LEFT JOIN CRM_MOTIVO_PERDAS cmp ON 
            cmp.cod_motivo_perda = ce.cod_motivo_perda
        LEFT JOIN produtos_modelos pm ON 
            pm.COD_PRODUTO = ce.COD_PRODUTO AND pm.COD_MODELO = ce.COD_MODELO
        LEFT JOIN caiuas_crm_eventos_descartados ced ON 
            ced.cod_empresa = ce.COD_EMPRESA AND ced.cod_evento = ce.COD_EVENTO
        WHERE
            ce.cod_tipo_evento IN (
                '829','831','795','793','797','799','819','821','785','807','815','817','810','812'
            )
            AND ce.status IN ('P')
        GROUP BY
            eu.cod_empresa
        ORDER BY 3 desc
        """
        cur_oracle.execute(query_empresas)
        dados_empresas = cur_oracle.fetchall()
        df_empresas = pd.DataFrame(dados_empresas, columns=[desc[0] for desc in cur_oracle.description])
        
        st.subheader("Acompanhamento de eventos Por Empresa")
        st.dataframe(df_empresas, hide_index=True)
        
        # Detalhamento de Eventos
        query_lista_eventos = f"""
        SELECT 
            concat('https://app.caiuas.com.br/crm/eventos/',concat(ce.cod_empresa, ce.COD_EVENTO)) link_evento,
            concat(ce.cod_empresa, ce.COD_EVENTO) evento,
            ce.NOME_CLIENTE_AVULSO ,
            TO_CHAR(
                CASE
                    WHEN ce.data_novo_contato IS NULL THEN ce.data_evento
                    ELSE ce.data_novo_contato
                END, 'YYYY-MM-DD'
            ) AS data_contato,
            ce.STATUS,
            cet.DESC_TIPO_EVENTO,
            eu.NOME_COMPLETO responsavel,
            ca.ANDAMENTO andamento_atendimento,
            ce.TERMOMETRO ,
            ce.COD_PROPOSTA
        FROM crm_eventos ce
        LEFT JOIN empresas_usuarios eu ON 1=1
            AND eu.nome = ce.RESPONSAVEL_PELO_EVENTO 
        LEFT JOIN CRM_ANDAMENTO ca ON 1=1
            AND ca.COD_ANDAMENTO = ce.COD_ANDAMENTO 
        LEFT JOIN CRM_EVENTOS_TIPO cet ON 1=1
            AND cet.COD_TIPO_EVENTO = ce.COD_TIPO_EVENTO 
        LEFT JOIN clientes c ON 1=1
            AND c.COD_CLIENTE = ce.COD_CLIENTE 
        WHERE 1=1
            AND ce.cod_tipo_evento IN (
            '829','831','795','793','797','799','819','821','785','807','815','817','810','812'
            )
            AND ce.status IN ('P')
        ORDER BY 4
        """
        cur_oracle.execute(query_lista_eventos)
        dados_lista_eventos = cur_oracle.fetchall()
        df_lista_eventos = pd.DataFrame(dados_lista_eventos, columns=[desc[0] for desc in cur_oracle.description])
        df_lista_eventos.columns = df_lista_eventos.columns.str.lower()
        
        df_lista_eventos['responsavel'] = df_lista_eventos['responsavel'].fillna('SEM RESPONSÁVEL')
        
        st.subheader("Lista de Eventos")
        
        opcoes_resp_evento = ['Todos'] + sorted(df_lista_eventos['responsavel'].unique().tolist())
        filtro_resp_evento = st.selectbox("Filtrar por responsável", opcoes_resp_evento, key="ad_filtro_resp_evento")
        
        df_lista_eventos_filtrado = df_lista_eventos.copy()
        if filtro_resp_evento != 'Todos':
            df_lista_eventos_filtrado = df_lista_eventos_filtrado[df_lista_eventos_filtrado['responsavel'] == filtro_resp_evento]
        cols = [c for c in df_lista_eventos_filtrado.columns if c not in ['link_evento', 'status']] + ['link_evento']
        
        st.caption(f"{len(df_lista_eventos_filtrado)} evento(s)")
        st.dataframe(
            df_lista_eventos_filtrado[cols],
            hide_index=True,
            use_container_width=True,
            column_config={
                "link_evento": st.column_config.LinkColumn("Link", display_text="Abrir Evento")
            }
        )
        
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
                filtro_resp_det = st.selectbox("Filtrar por responsável", opcoes_resp_det, key="ad_filtro_resp_chat")
            with fcol_det2:
                filtro_status_det = st.selectbox("Filtrar por status", ['Todos', 'Aberto', 'Pendente', 'Adiado'], key="ad_filtro_status_chat")
        
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
            
        # Conversões Marketing - CHAT
        query = f"""
            SELECT DISTINCT ON (m.conversation_id)
                c.created_at,
                CASE
                    WHEN entry->'changes'->0->'value'->'messages'->0->'referral'->>'source_url' IS NOT NULL
                    THEN entry->'changes'->0->'value'->'messages'->0->'referral'->>'source_url'
                    ELSE c.custom_attributes->>'link_campanha'
                END AS link_campanha,
                --entry->'changes'->0->'value'->'messages'->0->'referral'->>'source_id' AS id_campanha,
                c.custom_attributes->>'evento_nbs' AS link_crm,
                u.name AS responsavel
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
                AND c.created_at::date >= DATE '{data_inicial_ad}'
                AND c.created_at::date <= DATE '{data_final_ad}'
            ORDER BY m.conversation_id, c.created_at
        """
        cur_chat.execute(query)
        conversoes_marketing = cur_chat.fetchall()
        conversoes_marketing = pd.DataFrame(conversoes_marketing, columns=[desc[0] for desc in cur_chat.description])
        
        def _parse_campanha(link):
            if not link or str(link).strip() == '':
                return ''
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(str(link))
            if 'hondacaiuas.com.br' not in parsed.netloc:
                return str(link)
            qs = parse_qs(parsed.query)
            source = qs.get('utm_source', [''])[0]
            if source.lower() == 'chatgpt.com':
                return 'CHATGPT'
            campaign = qs.get('utm_campaign', [''])[0]
            if not campaign:
                campaign = 'performance-max'
            if source or campaign:
                return f"{source}-{campaign}".lower()
            return str(link)
        
        conversoes_marketing['campanha'] = conversoes_marketing['link_campanha'].apply(_parse_campanha)
    
        # Remove links hondacaiuas.com.br sem utm_source nem gclid
        def _tem_rastreamento(link):
            if not link or str(link).strip() == '':
                return True
            l = str(link)
            if 'hondacaiuas.com.br' not in l:
                return True
            return 'utm_source' in l or 'gl_' in l
    
        conversoes_marketing = conversoes_marketing[conversoes_marketing['link_campanha'].apply(_tem_rastreamento)]
        conversoes_marketing['evento'] = conversoes_marketing['link_crm'].str.extract(r'eventos/(\d+)').astype(str)
        conversoes_marketing = conversoes_marketing.fillna('')
        conversoes_marketing['evento'] = conversoes_marketing['evento'].apply(lambda x: x if x.isdigit() else '')
        lista_eventos = [e.strip() for e in conversoes_marketing['evento'].tolist() if e and str(e).strip() not in ('', 'nan', 'None', 'NaN')]
        
        st.write(f"Total de conversões encontradas: {len(conversoes_marketing)}")
        st.dataframe(conversoes_marketing)
        
        # Propostas geradas para as conversões
        query = f"""
            SELECT 
            to_char(concat(cre.cod_empresa, cre.cod_evento)) evento,
            to_char(v.COD_PROPOSTA) COD_PROPOSTA, 
            vp.EMISSAO data_proposta, 
            vp.VENDEDOR cod_vendedor, 
            eu.NOME_COMPLETO nome_vendedor, 
            pm.DESCRICAO_MODELO modelo, 
            cor.DESCRICAO cor, 
            v.ANO_MODELO, 
            v.CHASSI_COMPLETO, 
            e.NOME empresa, 
            v.DATA_NOTA emissao,
            p.DESCRICAO patio,
            c.COD_CLIENTE, 
            c.NOME nome_cliente,
            CASE 
                WHEN v.novo_usado = 'U' THEN 'Usado'
                WHEN v.COD_PROPOSTA_INTERNET IS NOT NULL THEN 'Direta'
                ELSE 'Novo'
            END novo_usado,
            cf.PLACA,
            CASE
                WHEN c.COD_CID_COM <> NULL THEN cid_com.DESCRICAO
                WHEN c.COD_CID_RES <> NULL THEN cid_res.DESCRICAO 
                ELSE cid_cob.DESCRICAO 
            END cidade,
            to_char(ve.CONTROLE) numero_nota
        FROM veiculos v 
        LEFT JOIN produtos pr ON pr.COD_PRODUTO = v.COD_PRODUTO 
        LEFT JOIN CORES_EXTERNAS cor ON cor.COR_EXTERNA = v.COR_EXTERNA 
        LEFT JOIN produtos_modelos pm ON pm.COD_PRODUTO = v.COD_PRODUTO AND pm.COD_MODELO = v.COD_MODELO 
        LEFT JOIN VEICULOS_PROPOSTAS vp ON vp.CHASSI_RESUMIDO = v.CHASSI_RESUMIDO AND vp.STATUS_PROPOSTA <> 'C'
        LEFT JOIN clientes c ON c.COD_CLIENTE = vp.COD_CLIENTE 
        LEFT JOIN patio p ON p.COD_PATIO = v.COD_PATIO
        LEFT JOIN EMPRESAS_USUARIOS eu ON eu.NOME = vp.VENDEDOR 
        LEFT JOIN empresas_usuarios eu2 ON eu2.nome = vp.QUEM_APROVOU 
        LEFT JOIN empresas e ON e.cod_empresa = v.COD_EMPRESA
        LEFT JOIN CLIENTES_FROTA cf ON cf.chassi = v.CHASSI_COMPLETO AND cf.COD_CLIENTE = c.COD_CLIENTE AND cf.nome = vp.VENDEDOR 
        LEFT JOIN cidades cid_res ON cid_res.cod_cidades = c.COD_CID_RES AND cid_res.uf = c.UF_RES 
        LEFT JOIN cidades cid_com ON cid_com.cod_cidades = c.COD_CID_COM AND cid_com.uf = c.UF_COM 
        LEFT JOIN cidades cid_cob ON cid_cob.cod_cidades = c.COD_CID_COBRANCA AND cid_cob.uf = c.UF_COBRANCA 
        LEFT JOIN vendas ve ON 1=1
            AND ve.COD_PROPOSTA = v.COD_PROPOSTA 
            AND ve.STATUS = 0
        LEFT JOIN crm_eventos cre ON 1=1
            AND cre.status <> 'D'
            AND cre.COD_PROPOSTA = vp.COD_PROPOSTA
            AND cre.COD_TIPO_EVENTO IN (819,821,815,817,810,812,829,831,795,793,797,799,787,833,825,785,807,827,823)
        WHERE 1=1
            and v.status in ('V','A')
            AND concat(cre.cod_empresa, cre.cod_evento) in ({','.join([str(e) for e in lista_eventos])})
        ORDER BY pm.DESCRICAO_MODELO
        """ if lista_eventos else None
        if lista_eventos:
            cur_oracle.execute(query)
            propostas_conversoes = cur_oracle.fetchall()
            propostas_conversoes = pd.DataFrame(propostas_conversoes, columns=[desc[0] for desc in cur_oracle.description], dtype=str)
            propostas_conversoes.columns = propostas_conversoes.columns.str.lower()
        else:
            propostas_conversoes = pd.DataFrame(columns=['evento'])
            
        st.write(f"Total de propostas relacionadas às conversões: {len(propostas_conversoes)}")
        st.dataframe(propostas_conversoes)
        
        
        cur_oracle.close()
        conn_oracle.close()
    
    
    except Exception as e:
        st.error(f"Erro ao executar a consulta: {e}")
    