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

EMAILS_IMPLANTACAO = [
    "pablo.ti@caiuas.com.br",
]


def render():
    st.title("Acompanhamento de Implantação de Sistemas")
    # st.info("Em construção... 🚧")
    query = f"""
    SELECT ce.COD_EMPRESA, ce.COD_EVENTO, ce.STATUS, cet.DESC_TIPO_EVENTO , ca.ANDAMENTO , cd.DESCRICAO_DESCARTE,cct.tag, ce.OBS_MEMO  
    FROM CRM_EVENTOS ce
    LEFT JOIN EMPRESAS_USUARIOS eu ON
        1 = 1
        AND eu.nome = ce.RESPONSAVEL_PELO_EVENTO
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
    WHERE 1=1
        AND ce.cod_tipo_evento=831
    """
    conn_oracle, cur_oracle = oracle()
    cur_oracle.execute(query)
    result_oracle = cur_oracle.fetchall()
    columns = [desc[0] for desc in cur_oracle.description]
    df = pd.DataFrame(result_oracle, columns=columns)
    
    # replace none to ''
    df = df.fillna('')
    
    cur_oracle.close()
    conn_oracle.close()
    
    # adiciona botão de download de planilha
    excel_buffer = io.BytesIO()
    df.to_excel(excel_buffer, index=False, sheet_name="Implantação")
    excel_buffer.seek(0)
    st.download_button(
        label="📥 Download da planilha (Excel)",
        data=excel_buffer,
        file_name="implantacao.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    st.dataframe(df, hide_index=True, use_container_width=True)
    df = df[df['STATUS'] == 'P']
    pivot = pd.pivot_table(df, index=['STATUS','ANDAMENTO','TAG'], values='COD_EVENTO', aggfunc='count').reset_index()
    st.dataframe(pivot, hide_index=True, use_container_width=True)
    