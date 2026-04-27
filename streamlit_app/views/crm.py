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

EMAILS_CRM = [
    "pablo.ti@caiuas.com.br"
]


def render():
    st.title("Acompanhamento de CRM")
    data_inicial = st.sidebar.date_input("Data Inicial", datetime.now())
    data_final = st.sidebar.date_input("Data Final", datetime.now())
    query = f"""
                SELECT
                ce.COD_EVENTO ,
                cet.COD_GRUPO,
                cg.desc_grupo,
                ce.cod_tipo_evento,
                ce.status,
                oa.cod_os_agenda,
                CASE
                    WHEN pm.DESCRICAO_MODELO IS NOT NULL THEN pm.DESCRICAO_MODELO
                    ELSE pm2.descricao_modelo
                END modelo_veiculo, 
                cet.desc_tipo_evento,
                eu3.nome_completo agendador,
                ce.cod_empresa,
                oa.numero_os,
                o.status_os,
                cmp.desc_motivo motivo_perda,
                cd.descricao_descarte,
                (
                SELECT
                    LISTAGG(srv.DESCRICAO_SERVICO, ', ') WITHIN GROUP (
                    ORDER BY srv.DESCRICAO_SERVICO)
                FROM
                    OS_SERVICOS oss
                LEFT JOIN servicos srv ON
                    srv.cod_servico = oss.cod_servico
                WHERE
                    oss.NUMERO_OS = o.NUMERO_OS
                    AND oss.COD_EMPRESA = o.COD_EMPRESA) servicos,
                (SELECT LISTAGG(oar.descricao, ', ') WITHIN GROUP (ORDER BY oar.descricao)
                        FROM OS_AGENDA_RECLAMACAO oar
                            WHERE 1=1
                                AND oa.COD_OS_AGENDA  = oar.COD_OS_AGENDA 
                                AND oa.COD_EMPRESA = oar.COD_EMPRESA) reclamacoes
            FROM
                crm_eventos ce
            LEFT JOIN CRM_EVENTOS_TIPO cet ON
                1 = 1
                AND cet.COD_TIPO_EVENTO = ce.COD_TIPO_EVENTO
            left join CRM_DESCARTES cd on 1=1
                and cd.COD_DESCARTE = ce.COD_DESCARTE
            LEFT JOIN CRM_MOTIVO_PERDAS cmp ON 1=1
                AND cmp.cod_motivo_perda = ce.cod_motivo_perda
            LEFT JOIN CRM_GRUPO cg ON
                1 = 1
                AND cg.COD_GRUPO = cet.COD_GRUPO
            LEFT JOIN OS_AGENDA oa ON
                1 = 1
                AND oa.cod_empresa = ce.COD_EMPRESA
                AND oa.CRM_COD_EVENTO = ce.COD_EVENTO
            LEFT JOIN CLIENTES c ON 1=1
                AND c.COD_CLIENTE = oa.cod_cliente
            LEFT JOIN PRISMA_BOX pb ON 1=1
                AND pb.PRISMA = oa.PRISMA 
            LEFT JOIN produtos p ON 1=1
                AND p.COD_PRODUTO = oa.COD_PRODUTO 
            LEFT JOIN PRODUTOS_MODELOS pm ON 1=1
                AND pm.COD_PRODUTO = oa.COD_PRODUTO 
                AND pm.COD_MODELO = oa.COD_MODELO
            LEFT JOIN PRODUTOS_MODELOS pm2 ON 1=1
                AND pm2.COD_PRODUTO = ce.veic_COD_PRODUTO 
                AND pm2.COD_MODELO = ce.veic_COD_MODELO
            LEFT JOIN EMPRESAS_USUARIOS eu ON 1=1
                AND eu.nome = ce.RESPONSAVEL_PELO_EVENTO
            LEFT JOIN os o ON
                1 = 1
                AND o.NUMERO_OS = oa.NUMERO_OS
                AND o.COD_EMPRESA = oa.COD_EMPRESA
            LEFT JOIN empresas_usuarios eu3 ON 1=1
                AND eu3.NOME = oa.quem_abriu
            WHERE
                1 = 1
                AND ce.COD_EMPRESA IN (11, 33)
                AND ce.data_evento >= TO_DATE('{data_inicial}', 'YYYY-MM-DD')
                AND ce.data_evento <= TO_DATE('{data_final}', 'YYYY-MM-DD')
            """
    con, cur = oracle()
    cur.execute(query)
    results = cur.fetchall()
    df = pd.DataFrame(results, columns=[desc[0] for desc in cur.description], dtype=str)
    cur.close()
    con.close()
    df = df.replace({None: np.nan, 'None': np.nan})
    df.loc[df['STATUS'].astype(str).str.upper().eq('P'), 'STATUS'] = 'Pendente'
    df.loc[df['STATUS'].astype(str).str.upper().eq('E'), 'STATUS'] = 'Encerrado'
    df.loc[df['STATUS'].astype(str).str.upper().eq('D'), 'STATUS'] = 'Descartado'
    df.loc[df['STATUS'].astype(str).str.upper().eq('V'), 'STATUS'] = 'Visita Agendada'
    df.loc[df['STATUS'].astype(str).str.upper().eq('R'), 'STATUS'] = 'Remarcou'
    df.loc[df['STATUS'].astype(str).str.upper().eq('A'), 'STATUS'] = 'Evento tem ações'
    df = df[df['STATUS'] != 'Pendente']
    df.loc[~df['STATUS'].isin(['Descartado']), 'STATUS'] = 'Encerrado'
    df = df[df['COD_TIPO_EVENTO'] != '267']
    ciclo = df[df['COD_GRUPO'] == '-1'].reset_index(drop=True)
    df = df[df['COD_GRUPO'] != '-1'].reset_index(drop=True)
    df = df[df['COD_GRUPO'] == '3'].reset_index(drop=True)
    encerrados = pd.concat([df, ciclo], ignore_index=True)
    encerrados.loc[(encerrados['STATUS_OS'] != '1.0') & (encerrados['STATUS'] != 'Descartado'), 'STATUS'] = 'Encerrado com erro'
    encerrados.loc[encerrados['MOTIVO_PERDA'].notnull(), 'STATUS'] = 'CONTATO PERDIDO'
    str_cols = encerrados.select_dtypes(include=['object', 'string']).columns
    encerrados[str_cols] = encerrados[str_cols].map(
        lambda x: ''.join(ch for ch in unicodedata.normalize('NFKD', x) if not unicodedata.combining(ch)) if isinstance(x, str) else x
    )
    encerrados[str_cols] = encerrados[str_cols].map(
        lambda x: ' '.join(x.split()) if isinstance(x, str) else x
    )
    encerrados[str_cols] = encerrados[str_cols].map(lambda x: x.upper() if isinstance(x, str) else x)
    num = r'(?:\d{1,3}(?:[.,]\d{3})+|\d+)'
    pat = rf'((?:\bREVISAO\s+DE\s+{num}(?:(?:\s*KMS?)\b)?)|(?:\bREVISAO\s+{num}(?=\s*KMS?\b|\b)))'
    encerrados['NOME_REVISAO'] = encerrados['SERVICOS'].str.extract(pat, expand=False) if not encerrados['SERVICOS'].isnull().all() else np.nan
    encerrados['NOME_REVISAO'] = encerrados['NOME_REVISAO'].str.replace(' DE ', ' ', regex=False) if not encerrados['NOME_REVISAO'].isnull().all() else np.nan
    encerrados['NOME_REVISAO'] = encerrados['NOME_REVISAO'].str.replace('KMS', '', regex=False) if not encerrados['NOME_REVISAO'].isnull().all() else np.nan
    encerrados['NOME_REVISAO'] = encerrados['NOME_REVISAO'].str.replace('KM', '', regex=False) if not encerrados['NOME_REVISAO'].isnull().all() else np.nan
    encerrados['NOME_REVISAO'] = encerrados['NOME_REVISAO'].str.strip() if not encerrados['NOME_REVISAO'].isnull().all() else np.nan
    encerrados['TIPO_ATENDIMENTO'] = encerrados['DESC_TIPO_EVENTO'].str.split(' - ').str[-1]
    
    
    eventos_descartados = encerrados[encerrados['STATUS'] == 'DESCARTADO'].reset_index(drop=True)
    eventos_descartados_motivos = pd.pivot_table(
    eventos_descartados,
    index=['DESCRICAO_DESCARTE'],
    values=['COD_EVENTO'],
    aggfunc={'COD_EVENTO': 'count'}
    ).reset_index().rename(columns={'COD_EVENTO': 'TOTAL_EVENTOS'})
    # adicione o dataframe na metade esquerda da tela e um grafico na metade direita
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Eventos descartados por motivo")
        st.dataframe(eventos_descartados_motivos, hide_index=True)
    with col2:
        st.subheader("Gráfico de eventos descartados por motivo")
        fig = px.bar(eventos_descartados_motivos, x='DESCRICAO_DESCARTE', y='TOTAL_EVENTOS', text='TOTAL_EVENTOS')
        fig.update_traces(textposition='outside')
        fig.update_layout(yaxis_title='Total de Eventos', xaxis_title='Motivo de Descarte', uniformtext_minsize=8, uniformtext_mode='hide')
        st.plotly_chart(fig, use_container_width=True)
    
    
    filtro = (encerrados['STATUS'] != 'DESCARTADO') & (encerrados['STATUS_OS'].astype(str) == '1.0')
    eventos_encerrados_por_revisao = (
        pd.pivot_table(
            encerrados.loc[filtro],
            index='NOME_REVISAO',
            columns='TIPO_ATENDIMENTO',
            values='COD_EVENTO',
            aggfunc='count'
        )
        .fillna(0)
        .rename_axis(index=None, columns=None)
        .reset_index()
    )
    # rename first column to NOME_REVISAO
    eventos_encerrados_por_revisao = eventos_encerrados_por_revisao.rename(columns={'index': 'NOME REVISAO'})
    
    # total ativos x PASSANTES
    total_ativos = eventos_encerrados_por_revisao['ATIVO'].sum() if 'ATIVO' in eventos_encerrados_por_revisao.columns else 0
    total_passantes = eventos_encerrados_por_revisao['PASSANTE'].sum() if 'PASSANTE' in eventos_encerrados_por_revisao.columns else 0
    total_receptivos = eventos_encerrados_por_revisao['RECEPTIVO'].sum() if 'RECEPTIVO' in eventos_encerrados_por_revisao.columns else 0
    col3, col4 = st.columns(2)
    with col3:
        st.subheader("Eventos encerrados com SUCESSO ! por revisão")
        st.dataframe(eventos_encerrados_por_revisao, hide_index=True)
    with col4:
        st.subheader("Gráfico de Ativos vs. Passantes")
        
        # Cria um DataFrame para o gráfico de pizza
        df_pie = pd.DataFrame({
            'Tipo': ['Ativos', 'Passantes'],
            'Total': [total_ativos, total_passantes]
        })
        
        # Cria o gráfico de pizza
        fig2 = px.pie(df_pie, values='Total', names='Tipo', title='Comparativo Ativos vs. Passantes')
        fig2.update_traces(textposition='inside', textinfo='percent+label+value')
        st.plotly_chart(fig2, use_container_width=True)
    
    # exibir planilha grande de detalhamento para download
    st.subheader("Detalhamento dos eventos encerrados")
    planilha = io.BytesIO()
    with pd.ExcelWriter(planilha, engine='xlsxwriter') as writer:
        encerrados.to_excel(writer, index=False, sheet_name='Eventos Encerrados')
        eventos_descartados.to_excel(writer, index=False, sheet_name='Eventos Descartados')
        eventos_descartados_motivos.to_excel(writer, index=False, sheet_name='Descartes por Motivo')
        eventos_encerrados_por_revisao.to_excel(writer, index=False, sheet_name='Encerrados por Revisao')
        writer.close()
        planilha.seek(0)
        st.download_button(
            label="Download da planilha completa",
            data=planilha.getvalue(),
            file_name="acompanhamento_crm.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    col5, col6 = st.columns(2)
    eventos_encerrados_com_sucesso_por_tipo = (
        pd.pivot_table(
            encerrados.loc[filtro],
            index='DESC_TIPO_EVENTO',
            values='COD_EVENTO',
            aggfunc='count'
        )
        .fillna(0)
        .rename_axis(index=None)
        .reset_index()
        .rename(columns={'COD_EVENTO': 'TOTAL_EVENTOS'})
    )
    eventos_encerrados_com_sucesso_por_tipo.rename(columns={'index': 'TIPO ATENDIMENTO'}, inplace=True)
    # se total de eventos for maior que 0, exibir
    
    if not eventos_encerrados_com_sucesso_por_tipo.empty and eventos_encerrados_com_sucesso_por_tipo['TOTAL_EVENTOS'].sum() > 0:
        with col5:
            st.subheader("Eventos encerrados com SUCESSO ! por tipo de atendimento")
            st.dataframe(eventos_encerrados_com_sucesso_por_tipo, hide_index=True)
        with col6:
            st.subheader("Gráfico de eventos encerrados com SUCESSO ! por tipo de atendimento")
            fig3 = px.bar(eventos_encerrados_com_sucesso_por_tipo, x='TIPO ATENDIMENTO', y='TOTAL_EVENTOS', text='TOTAL_EVENTOS', title="Total de Eventos por Tipo de Atendimento")
            fig3.update_traces(textposition='outside')
            fig3.update_layout(yaxis_title='Total de Eventos', xaxis_title='Tipo de Atendimento', uniformtext_minsize=8, uniformtext_mode='hide', xaxis_tickangle=-45)
            st.plotly_chart(fig3, use_container_width=True)
    