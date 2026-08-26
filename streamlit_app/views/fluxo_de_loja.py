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

EMAILS_CRM_SHOWROOM = [
    "pablo.ti@caiuas.com.br",
    "cristiane.aguilar@caiuas.com.br","nathalli.pereira@caiuas.com.br",
    "cristiane.aguilar@caiuas.com.br","nathalli.pereira@caiuas.com.br",
    "franciele.mayer@caiuas.com.br",
    "gabrieli.auditoria@caiuas.com.br"
]


def render():
    st.title("Acompanhamento de Fluxo de Loja")
    # st.write("Em desenvolvimento...")
    data_inicial = st.sidebar.date_input("Data Inicial", datetime.now())
    data_final = st.sidebar.date_input("Data Final", datetime.now())
    query = f"""
        SELECT 
            eu.cod_empresa,
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
            --ce.data_agendada,
            --ce.data_visita,
            ce.cod_proposta,
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
            ce.data_criacao,
            ce.COD_TIPO_EVENTO,
            TRUNC(cel.data_criacao) data_lead,
            CASE
                WHEN eu_lead.NOME_COMPLETO IS NOT NULL THEN upper(eu_lead.NOME_COMPLETO)
                ELSE 'SEM RESPONSÁVEL'
            END responsavel_lead,
            TRUNC(cel.data_agendada) data_agendada_lead,
            vp.STATUS_PROPOSTA,
            TRIM(TO_CHAR(ce.COD_EMPRESA_ANTERIOR)) || TRIM(TO_CHAR(ce.COD_EVENTO_ANTERIOR)) cod_evento_anterior
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
            LEFT JOIN crm_eventos cel ON 1=1
                AND ce.COD_EVENTO_ANTERIOR = cel.COD_EVENTO
                AND ce.COD_EMPRESA_ANTERIOR = cel.COD_EMPRESA
            LEFT JOIN EMPRESAS_USUARIOS eu_lead ON 1=1
                AND eu_lead.NOME = cel.RESPONSAVEL_PELO_EVENTO
            LEFT JOIN VEICULOS_PROPOSTAS vp ON 1=1
            	AND vp.COD_PROPOSTA = ce.COD_PROPOSTA
            WHERE 1=1
                AND ce.COD_TIPO_EVENTO IN (785,807)
                AND ce.status <> 'D'
                AND TRUNC(ce.DATA_CRIACAO) >= TO_DATE('{data_inicial}', 'YYYY-MM-DD') AND TRUNC(ce.DATA_CRIACAO) <= TO_DATE('{data_final}', 'YYYY-MM-DD')
    """
    con, cur = oracle()
    cur.execute(query)
    results = cur.fetchall()
    df = pd.DataFrame(results, columns=[desc[0] for desc in cur.description], dtype=str)
    query = f"""
        SELECT 
        eu.cod_empresa,
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
        --ce.data_agendada,
        --ce.data_visita,
        ce.cod_proposta,
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
        ce.data_criacao,
        ce.COD_TIPO_EVENTO,
        TRUNC(cel.data_criacao) data_lead,
        CASE
            WHEN eu_lead.NOME_COMPLETO IS NOT NULL THEN upper(eu_lead.NOME_COMPLETO)
            ELSE 'SEM RESPONSÁVEL'
        END responsavel_lead,
        TRUNC(cel.data_agendada) data_agendada_lead,
        vp.STATUS_PROPOSTA,
        TRIM(TO_CHAR(ce.COD_EMPRESA_ANTERIOR)) || TRIM(TO_CHAR(ce.COD_EVENTO_ANTERIOR)) cod_evento_anterior
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
        LEFT JOIN crm_eventos cel ON 1=1
            AND ce.COD_EVENTO_ANTERIOR = cel.COD_EVENTO
            AND ce.COD_EMPRESA_ANTERIOR = cel.COD_EMPRESA
        LEFT JOIN EMPRESAS_USUARIOS eu_lead ON 1=1
            AND eu_lead.NOME = cel.RESPONSAVEL_PELO_EVENTO
        LEFT JOIN VEICULOS_PROPOSTAS vp ON 1=1
            AND vp.COD_PROPOSTA = ce.COD_PROPOSTA
        WHERE 1=1
            AND ce.COD_TIPO_EVENTO IN (819,821,815,817,810,812,829,
                795,
                793,
                797,
                799,
                810,
812,
837)
            AND ce.status <> 'D'
            AND TRUNC(ce.DATA_VISITA) >= TO_DATE('{data_inicial}', 'YYYY-MM-DD') AND TRUNC(ce.DATA_VISITA) <= TO_DATE('{data_final}', 'YYYY-MM-DD')
    """
    cur.execute(query)
    results = cur.fetchall()
    df_visitas = pd.DataFrame(results, columns=[desc[0] for desc in cur.description], dtype=str)
    # concatena df e df_visitas
    df = pd.concat([df, df_visitas], ignore_index=True)
    
    
    # remova o .0 do cod_proposta ele é SRT
    df['COD_PROPOSTA'] = df['COD_PROPOSTA'].str.replace('.0', '', regex=False)
    
    # se status_proposta = 'V' altere o status do evento para "Faturado", se tiver proposta e se status da proposta for "C" altere o status do evento para proposta cancelada, se for outro adicione Aguardando cancelamento
    df['STATUS'] = df.apply(lambda row: 'Faturado' if row['STATUS_PROPOSTA'] == 'V' else ('Proposta Cancelada' if row['STATUS_PROPOSTA'] == 'C' else ('Aguardando faturamento' if row['STATUS_PROPOSTA'] not in ['V', 'C', None, ''] else row['STATUS'])), axis=1)
    df['STATUS_ATENDIMENTO'] = df.apply(lambda row: 'Faturado' if row['STATUS_PROPOSTA'] == 'V' else ('Proposta Cancelada' if row['STATUS_PROPOSTA'] == 'C' else ('Aguardando faturamento' if row['STATUS_PROPOSTA'] not in ['V', 'C', None, ''] else row['STATUS'])), axis=1)
    
    
    
    query = f"""
    SELECT
        ccr.cod_empresa,
        concat(ce.COD_EMPRESA, ce.COD_EVENTO) cod_evento,
        TRUNC(ccr.created_at) data_retorno,
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
            WHEN ce.COD_CLIENTE = 1 THEN ce.NOME_CLIENTE_AVULSO
            ELSE c.NOME
        END nome_cliente,
        ce.cod_proposta,
        upper(cet.DESC_TIPO_EVENTO) tipo_evento,
        CASE
            WHEN eu.NOME_COMPLETO IS NOT NULL THEN upper(eu.NOME_COMPLETO)
            ELSE 'SEM RESPONSÁVEL'
        END responsavel,
        CASE
            WHEN ce.cod_modelo IS NOT NULL THEN pm.descricao_modelo
            ELSE 'VEÍCULO NAO DEFINIDO'
        END veiculo,
        (SELECT count(*) FROM CAIUAS_CRM_RETORNO ccr2
         WHERE ccr2.COD_EMPRESA = ce.COD_EMPRESA
           AND ccr2.COD_EVENTO = ce.COD_EVENTO) qtd_retornos,
        CASE
            WHEN (SELECT count(*) FROM caiuas_crm_test_drive cctd WHERE cctd.COD_EMPRESA = ce.COD_EMPRESA AND cctd.COD_EVENTO = ce.COD_EVENTO) > 0 THEN 'TEM'
            ELSE 'NÃO'
        END tem_test_drive,
        TRUNC(ce.data_criacao) data_criacao
    FROM CAIUAS_CRM_RETORNO ccr
    LEFT JOIN crm_eventos ce ON 1=1
        AND ce.COD_EVENTO = ccr.COD_EVENTO
        AND ce.COD_EMPRESA = ccr.COD_EMPRESA
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
    LEFT JOIN crm_eventos cel ON 1=1
        AND ce.COD_EVENTO_ANTERIOR = cel.COD_EVENTO 
        AND ce.COD_EMPRESA_ANTERIOR = cel.COD_EMPRESA
    WHERE 1=1
        AND ce.status <> 'D'
        and ce.COD_TIPO_EVENTO IN (819,821,815,817,810,812,829,
                795,
                793,
                797,
                799,
                810,
812,
837)
        AND TRUNC(ccr.created_at) >= TO_DATE('{data_inicial}', 'YYYY-MM-DD')
        AND TRUNC(ccr.created_at) <= TO_DATE('{data_final}', 'YYYY-MM-DD')
    """
    cur.execute(query)
    results = cur.fetchall()
    df_retorno = pd.DataFrame(results, columns=[desc[0] for desc in cur.description])
    
    cur.close()
    con.close()
    
    # Converter colunas de data para datetime
    df['DATA_CONTATO'] = pd.to_datetime(df['DATA_CONTATO'], errors='coerce')
    
    # Formatar datas como string (YYYY-MM-DD) e substituir NaT por string vazia
    df['DATA_CONTATO'] = df['DATA_CONTATO'].dt.strftime('%Y-%m-%d').fillna('-')
    df['DATA_LEAD'] = pd.to_datetime(df['DATA_LEAD'], errors='coerce')
    df['DATA_LEAD'] = df['DATA_LEAD'].dt.strftime('%Y-%m-%d').fillna('-')
    df['DATA_AGENDADA_LEAD'] = pd.to_datetime(df['DATA_AGENDADA_LEAD'], errors='coerce')
    df['DATA_AGENDADA_LEAD'] = df['DATA_AGENDADA_LEAD'].dt.strftime('%Y-%m-%d').fillna('-')
    
    # Substituir None/NaN nas demais colunas
    df = df.fillna('-')
    df['COD_EVENTO_ANTERIOR'] = df['COD_EVENTO_ANTERIOR'].replace('-', '')
    df['link_fluxo'] = df['COD_EVENTO'].apply(lambda x: f"https://app.caiuas.com.br/crm/eventos/{x}")
    df['link_lead'] = df['COD_EVENTO_ANTERIOR'].apply(
        lambda x: f"https://app.caiuas.com.br/crm/eventos/{x}" if str(x).strip() != '' else ''
    )
    
    df_retorno['DATA_RETORNO'] = pd.to_datetime(df_retorno['DATA_RETORNO'], errors='coerce')
    df_retorno['DATA_RETORNO'] = df_retorno['DATA_RETORNO'].dt.strftime('%Y-%m-%d').fillna('-')
    df_retorno['DATA_CRIACAO'] = pd.to_datetime(df_retorno['DATA_CRIACAO'], errors='coerce')
    df_retorno['DATA_CRIACAO'] = df_retorno['DATA_CRIACAO'].dt.strftime('%Y-%m-%d').fillna('-')
    df_retorno = df_retorno.fillna('-')
    df_retorno['LINK'] = df_retorno['COD_EVENTO'].apply(lambda x: f"https://app.caiuas.com.br/crm/eventos/{x}")

    atendimentos_por_vendedor = (
        df.groupby(['RESPONSAVEL', 'VEICULO'])['COD_EVENTO']
        .count()
        .reset_index()
        .rename(columns={
            'RESPONSAVEL': 'RESPONSAVEL',
            'VEICULO': 'VEICULO',
            'COD_EVENTO': 'QUANTIDADE'
        })
        .sort_values(['RESPONSAVEL', 'QUANTIDADE', 'VEICULO'], ascending=[True, False, True])
    )
    
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name="Primeira passagem")
        df_retorno.to_excel(writer, index=False, sheet_name="Retornos")
        atendimentos_por_vendedor.to_excel(writer, index=False, sheet_name="Atendimentos por vendedor")
    excel_buffer.seek(0)
    st.download_button(
        label="Download da planilha de eventos",
        data=excel_buffer,
        file_name="eventos_fluxo_de_loja.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    
    empresa_selecionada = st.sidebar.selectbox("Filtrar por empresa", ["Todas", '11', '33'])
    if empresa_selecionada != "Todas":
        df = df[df['COD_EMPRESA'] == empresa_selecionada]
    
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
    
    # Buscar feriados no período para cálculo de média
    con_fer, cur_fer = oracle()
    cur_fer.execute(f"""
        SELECT TRUNC(DATA) AS DATA
        FROM FERIADO
        WHERE TRUNC(DATA) >= TO_DATE('{data_inicial}', 'YYYY-MM-DD')
          AND TRUNC(DATA) <= TO_DATE('{data_final}', 'YYYY-MM-DD')
        GROUP BY TRUNC(DATA)
    """)
    feriados_resultado = cur_fer.fetchall()
    cur_fer.close()
    con_fer.close()
    datas_feriados = set()
    for row in feriados_resultado:
        v = row[0]
        if hasattr(v, 'date'):
            datas_feriados.add(v.date())
        elif v is not None:
            import datetime as _dt
            try:
                datas_feriados.add(_dt.date.fromisoformat(str(v)[:10]))
            except Exception:
                pass
    
    # Calcular dias úteis (Seg-Sáb) no período excluindo feriados
    todas_datas = pd.date_range(data_inicial, data_final, freq='D')
    dias_uteis = [d for d in todas_datas if d.weekday() < 6 and d.date() not in datas_feriados]
    num_dias_uteis = len(dias_uteis)
    
    # Gráfico: Total de Primeiras Passagens vs Retornos
    total_primeiras = len(df)
    total_retornos = len(df_retorno)
    media_por_dia = round(total_primeiras / num_dias_uteis, 1) if num_dias_uteis > 0 else 0
    df_comparativo = pd.DataFrame({
        "Tipo": ["Primeiras Passagens", "Retornos"],
        "Total": [total_primeiras, total_retornos]
    })
    col_chart1, col_chart2, col_chart3 = st.columns([1, 2, 2])
    with col_chart1:
        st.markdown(f"""
        <div style="text-align: center;">
            <p style="font-size: 14px; color: gray; margin-bottom: 0;">Primeiras Passagens</p>
            <p style="font-size: 2rem; font-weight: bold; margin: 0 0 16px 0;">{total_primeiras}</p>
            <p style="font-size: 14px; color: gray; margin-bottom: 0;">Retornos</p>
            <p style="font-size: 2rem; font-weight: bold; margin: 0 0 16px 0;">{total_retornos}</p>
            <p style="font-size: 14px; color: gray; margin-bottom: 0;">Média/dia <span style="font-size: 12px;">(Seg-Sáb s/ feriados)</span></p>
            <p style="font-size: 2rem; font-weight: bold; margin: 0;">{media_por_dia}</p>
            <p style="font-size: 12px; color: gray; margin-top: 2px;">{num_dias_uteis} dias úteis no período</p>
        </div>
        """, unsafe_allow_html=True)
    with col_chart2:
        fig_comparativo = px.bar(
            df_comparativo,
            x="Tipo",
            y="Total",
            text="Total",
            color="Tipo",
            color_discrete_map={"Primeiras Passagens": "#3498db", "Retornos": "#e67e22"},
            title="Primeiras Passagens vs Retornos no período"
        )
        fig_comparativo.update_traces(textposition='outside')
        fig_comparativo.update_layout(showlegend=False, yaxis_title="Total", xaxis_title="")
        st.plotly_chart(fig_comparativo, use_container_width=True)
    with col_chart3:
        st.markdown("**Eventos por Status de Atendimento**")
        df_status_atendimento = (
            df.groupby('STATUS_ATENDIMENTO')['COD_EVENTO']
            .count()
            .reset_index()
            .rename(columns={'STATUS_ATENDIMENTO': 'Status', 'COD_EVENTO': 'Quantidade'})
            .sort_values('Quantidade', ascending=False)
        )
        st.dataframe(df_status_atendimento, hide_index=True, use_container_width=True)
    
    # Seção com 3 colunas de indicadores
    st.subheader("Indicadores")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Gráfico de pizza - Test Drive
        test_drive_counts = df['TEM_TEST_DRIVE'].value_counts().reset_index()
        test_drive_counts.columns = ['Test Drive', 'Quantidade']
        test_drive_counts['Test Drive'] = test_drive_counts['Test Drive'].replace({'TEM': 'Sim', 'NÃO': 'Não'})
        
        fig_test_drive = px.pie(
            test_drive_counts, 
            values='Quantidade', 
            names='Test Drive', 
            title='Eventos com Test Drive',
            color='Test Drive',
            color_discrete_map={'Sim': '#2ecc71', 'Não': '#e74c3c'}
        )
        fig_test_drive.update_traces(textposition='inside', textinfo='percent+label+value')
        st.plotly_chart(fig_test_drive, use_container_width=True)
    
    with col2:
        eventos_por_responsavel = df.groupby('RESPONSAVEL')['COD_EVENTO'].count().reset_index()
        eventos_por_responsavel.columns = ['Responsável', 'Quantidade']
        eventos_por_responsavel = eventos_por_responsavel.sort_values('Quantidade', ascending=True)
        
        fig_responsavel = px.bar(
            eventos_por_responsavel,
            x='Quantidade',
            y='Responsável',
            orientation='h',
            title='Eventos por Responsável',
            color='Quantidade',
            color_continuous_scale='Blues'
        )
        fig_responsavel.update_layout(
            showlegend=False,
            coloraxis_showscale=False,
            yaxis={'categoryorder': 'total ascending'},
            height=400
        )
        st.plotly_chart(fig_responsavel, use_container_width=True)
    
    with col3:
        # Gráfico de barras - Eventos por Veículo
        eventos_por_veiculo = df.groupby('VEICULO')['COD_EVENTO'].count().reset_index()
        eventos_por_veiculo.columns = ['Veículo', 'Quantidade']
        eventos_por_veiculo = eventos_por_veiculo.sort_values('Quantidade', ascending=True)
        
        fig_veiculo = px.bar(
            eventos_por_veiculo,
            x='Quantidade',
            y='Veículo',
            orientation='h',
            title='Eventos por Veículo',
            color='Quantidade',
            color_continuous_scale='Greens'
        )
        fig_veiculo.update_layout(
            showlegend=False,
            coloraxis_showscale=False,
            yaxis={'categoryorder': 'total ascending'},
            height=400
        )
        st.plotly_chart(fig_veiculo, use_container_width=True)
    # divisor para mais tre colunas
    # st.markdown("---")
    # col4, col5, col6 = st.columns(3)
    # with col4:
    #     # nada
    #     st.empty()
    # with col5:
    #     st.empty()
    # with col6:
    #     st.empty()
        
    
    
    # Tabela: Primeiras passagens por modelo de veículo
    st.subheader("Primeiras passagens por modelo de veículo")
    eventos_por_modelo = (
        df.groupby('VEICULO')['COD_EVENTO']
        .count()
        .reset_index()
        .rename(columns={'VEICULO': 'Modelo', 'COD_EVENTO': 'Quantidade'})
        .sort_values('Quantidade', ascending=False)
    )
    st.dataframe(eventos_por_modelo, hide_index=True)
    
    # Tabela: Passagens Varejo - CRIS (apenas tipo 785)
    st.subheader("Passagens Varejo - CRIS")
    df_varejo_cris = df[df['COD_TIPO_EVENTO'].isin(['785','815','810'])]
    varejo_cris_por_modelo = (
        df_varejo_cris.groupby('VEICULO')['COD_EVENTO']
        .count()
        .reset_index()
        .rename(columns={'VEICULO': 'Modelo', 'COD_EVENTO': 'Quantidade'})
        .sort_values('Quantidade', ascending=False)
    )
    st.dataframe(varejo_cris_por_modelo, hide_index=True)
    
    st.subheader("Eventos")
    st.dataframe(
        df, 
        hide_index=True,
        column_config={
            "link_fluxo": st.column_config.LinkColumn(
                "Link Fluxo",
                display_text="Abrir"
            ),
            "link_lead": st.column_config.LinkColumn(
                "Link Lead",
                display_text="Abrir"
            ),
        }
    )
    
    st.subheader("Retornos")
    st.dataframe(
        df_retorno,
        hide_index=True,
        column_config={
            "LINK": st.column_config.LinkColumn(
                "Abrir Evento",
                display_text="Abrir"
            )
        }
    )
    
    st.subheader("Propostas Faturadas")
    query_faturadas = f"""
    SELECT 
        vp.VENDEDOR, 
        vp.cod_proposta, 
        vp.STATUS_PROPOSTA, 
        vp.COD_CLIENTE, 
        c.NOME, 
        c.TELEFONE_CEL, 
        c.TELEFONE_COM, 
        c.TELEFONE_RES, 
        c.TELEFONE_FAX, 
        ce.FONE_CLIENTE_AVULSO,
        --CASE
        --    WHEN ce.COD_EVENTO IS NOT NULL THEN concat('https://app.caiuas.com.br/crm/eventos/',concat(ce.COD_EMPRESA, ce.COD_EVENTO))
        --    ELSE null
        --END link_fluxo,
        CASE
            WHEN ce.COD_EVENTO_ANTERIOR IS NOT NULL THEN concat('https://app.caiuas.com.br/crm/eventos/',concat(ce.COD_EMPRESA_ANTERIOR, ce.COD_EVENTO_ANTERIOR))
            ELSE null
        END link_lead
    FROM VEICULOS_PROPOSTAS vp 
    LEFT JOIN clientes c ON 1=1
        AND c.COD_CLIENTE = vp.COD_CLIENTE 
    LEFT JOIN CRM_EVENTOS ce ON 1=1
        AND ce.COD_PROPOSTA = vp.COD_PROPOSTA 
        AND ce.COD_TIPO_EVENTO IN (785,807,819,821,815,817,810,812)
    --LEFT JOIN CRM_EVENTOS ce2 ON 1=1
    --    AND ce2.COD_PROPOSTA = ce.COD_EVENTO_ANTERIOR 
    --    AND ce2.COD_EMPRESA = ce.COD_EMPRESA_ANTERIOR 
    WHERE 1=1
        AND TRUNC(vp.DATA_VENDA) >= TO_DATE('{data_inicial}', 'YYYY-MM-DD')
        AND TRUNC(vp.DATA_VENDA) <= TO_DATE('{data_final}', 'YYYY-MM-DD')
        AND vp.STATUS_PROPOSTA = 'V'
    ORDER BY vp.VENDEDOR, vp.COD_PROPOSTA
    """
    con_fat, cur_fat = oracle()
    cur_fat.execute(query_faturadas)
    results_fat = cur_fat.fetchall()
    df_faturadas = pd.DataFrame(results_fat, columns=[desc[0] for desc in cur_fat.description])
    cur_fat.close()
    con_fat.close()
    df_faturadas = df_faturadas.fillna('')
    df_faturadas.columns = [c.lower() for c in df_faturadas.columns]
    
    excel_buffer_fat = io.BytesIO()
    with pd.ExcelWriter(excel_buffer_fat, engine='xlsxwriter') as writer:
        df_faturadas.to_excel(writer, index=False, sheet_name="Propostas Faturadas")
    excel_buffer_fat.seek(0)
    st.download_button(
        label="Download Propostas Faturadas",
        data=excel_buffer_fat,
        file_name="propostas_faturadas.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    st.dataframe(
        df_faturadas,
        hide_index=True,
        use_container_width=True,
        column_config={
            "link_fluxo": st.column_config.LinkColumn("Link Fluxo", display_text="Abrir"),
            "link_lead": st.column_config.LinkColumn("Link Lead", display_text="Abrir"),
        }
    )
    