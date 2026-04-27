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
    "pablo.ti@caiuas.com.br",
    "marcelotcf@caiuas.com.br",
    "duda@pantys.com.br"
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
    