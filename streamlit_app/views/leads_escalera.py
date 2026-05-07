import streamlit as st
import requests
import jwt
from datetime import datetime
import plotly.express as px
from database import oracle, chatwoot
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
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

EMAILS_ESCALERA = [
    "pablo.ti@caiuas.com.br",
    "rafael@escaleraconsultoria.com.br",
    "cristiane.aguilar@caiuas.com.br"
]


def render():
    st.title("Leads Escalera")
    data_inicial_chat = st.sidebar.date_input("Data Inicial", datetime.now().date(), key="escalera_data_inicial")
    data_final_chat = st.sidebar.date_input("Data Final", datetime.now().date(), key="escalera_data_final")
    
    data_inicial_query = data_inicial_chat - timedelta(days=7)
    
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
    WHERE 1=1
        AND (
            entry->'changes'->0->'value'->'messages'->0->'referral' IS NOT NULL
            OR
            c.custom_attributes->>'link_campanha' IS NOT NULL
        )
        AND c.created_at::date >= DATE '{data_inicial_query}'
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
    
    df_chatwoot_full = df_chatwoot.copy()
    
    if not df_chatwoot_full.empty:
        df_chatwoot_full['created_at_dt'] = pd.to_datetime(df_chatwoot_full['created_at'], errors='coerce')
        df_chatwoot_full['date_only'] = df_chatwoot_full['created_at_dt'].dt.date
        
        mask_current = (df_chatwoot_full['date_only'] >= data_inicial_chat) & (df_chatwoot_full['date_only'] <= data_final_chat)
        mask_past = (df_chatwoot_full['date_only'] >= (data_inicial_chat - timedelta(days=7))) & (df_chatwoot_full['date_only'] <= (data_final_chat - timedelta(days=7)))
        
        df_chatwoot = df_chatwoot_full[mask_current].copy()
        df_past = df_chatwoot_full[mask_past].copy()
    else:
        df_past = pd.DataFrame()
    
    df_chatwoot = df_chatwoot.fillna('')
    df_chatwoot = df_chatwoot.replace('None', '')
    df_chatwoot['link_chat'] = df_chatwoot.apply(
        lambda row: f"https://chat.caiuas.com.br/app/accounts/{row['account_id']}/conversations/{row['conversation_id']}"
        if str(row.get('account_id', '')).strip() != '' and str(row.get('conversation_id', '')).strip() != ''
        else '',
        axis=1
    )
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
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
    
    with col2:
        st.subheader("Evolução de Eventos Criados")
        
        if data_inicial_chat == data_final_chat:
            lbl_atual = data_inicial_chat.strftime('%d/%m/%Y')
            lbl_passada = (data_inicial_chat - timedelta(days=7)).strftime('%d/%m/%Y')
        else:
            lbl_atual = f"Atual ({data_inicial_chat.strftime('%d/%m')} a {data_final_chat.strftime('%d/%m')})"
            data_ini_passada = data_inicial_chat - timedelta(days=7)
            data_fim_passada = data_final_chat - timedelta(days=7)
            lbl_passada = f"Semana Passada ({data_ini_passada.strftime('%d/%m')} a {data_fim_passada.strftime('%d/%m')})"
        
        chart_data = []
        if not df_chatwoot.empty:
            curr_grp = df_chatwoot.groupby('date_only').size().reset_index(name='Qtd')
            curr_grp['Período'] = lbl_atual
            curr_grp['Data Alinhada'] = pd.to_datetime(curr_grp['date_only'])
            chart_data.append(curr_grp)
        
        if not df_past.empty:
            past_grp = df_past.groupby('date_only').size().reset_index(name='Qtd')
            past_grp['Período'] = lbl_passada
            aligned = pd.to_datetime(past_grp['date_only']) + pd.Timedelta(days=7)
            past_grp['Data Alinhada'] = aligned
            chart_data.append(past_grp)
        
        if chart_data:
            df_chart = pd.concat(chart_data, ignore_index=True)
            df_chart = df_chart.sort_values('Data Alinhada')
            fig = px.line(
                df_chart, 
                x='Data Alinhada', 
                y='Qtd', 
                color='Período', 
                markers=True,
                color_discrete_sequence=['#e63946', '#a8dadc'] # Vermelho e Azul claro
            )
            fig.update_layout(
                xaxis_title="Dia", 
                yaxis_title="Quantidade de Eventos", 
                legend_title="", 
                margin=dict(t=20, b=40),
                legend=dict(
                    orientation="h",
                    yanchor="top",
                    y=-0.2,
                    xanchor="center",
                    x=0.5
                )
            )
            fig.update_xaxes(tickformat="%d/%m")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Nenhum dado para exibir o gráfico no período.")

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
            CASE 
                WHEN ce.COD_PROPOSTA IS NOT NULL THEN 'Super quente'
                
                WHEN ce.TERMOMETRO = 1 THEN 'Frio'
                WHEN ce.TERMOMETRO = 2 THEN 'Morno'
                WHEN ce.TERMOMETRO = 3 THEN 'Quente'
                ELSE 'Não classificado'
            END AS termometro,
            ce.COD_PROPOSTA
        FROM crm_eventos ce
        LEFT JOIN empresas_usuarios eu ON 1=1
            AND eu.nome = ce.RESPONSAVEL_PELO_EVENTO
        LEFT JOIN CRM_ANDAMENTO ca ON 1=1
            AND ca.COD_ANDAMENTO = ce.COD_ANDAMENTO
        WHERE concat(ce.COD_EMPRESA, ce.COD_EVENTO) IN ({in_clause})
        """
        try:
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

        except Exception as e:
            st.error("Ops falha ao se comunicar com o NBS, tente aperta R no seu teclado ou recarregar a página"            )

        except Exception as e:
            st.error("Ops falha ao se comunicar com o NBS, tente aperta R no seu teclado ou recarregar a página")

    st.subheader("Campanhas (Chatwoot)")
    total_linhas_chatwoot = len(df_chatwoot)
    excel_buffer_chatwoot = io.BytesIO()
    df_export = df_chatwoot_excel.drop(columns=['link_crm', 'link_chat'], errors='ignore').copy()

    if 'created_at' in df_export.columns:
        df_export['created_at'] = pd.to_datetime(df_export['created_at'], errors='coerce').dt.tz_localize(None)

    with pd.ExcelWriter(excel_buffer_chatwoot, engine='xlsxwriter') as writer:
        df_export.to_excel(writer, index=False, sheet_name="Chatwoot", startrow=1)
        workbook = writer.book
        worksheet = writer.sheets["Chatwoot"]

        worksheet.set_row(0, 50)
        try:
            worksheet.insert_image('A1', 'logo.png', {'x_scale': 0.6, 'y_scale': 0.6, 'x_offset': 5, 'y_offset': 5})
        except Exception:
            pass

        title_format = workbook.add_format({
            'bold': True,
            'font_size': 32,
            'align': 'center',
            'valign': 'vcenter',
            'font_name': 'Calibri'
        })

        max_col_index = len(df_export.columns) - 1
        if max_col_index >= 1:
            worksheet.merge_range(0, 1, 0, max_col_index, 'Leads Caiuás', title_format)
        else:
            worksheet.write(0, 1, 'Leads Caiuás', title_format)

        datetime_format = workbook.add_format({'num_format': 'dd/mm/yyyy hh:mm'})

        for i, col in enumerate(df_export.columns):
            max_len = max(df_export[col].astype(str).map(len).max(), len(str(col))) + 2
            if col == 'created_at':
                worksheet.set_column(i, i, max(max_len, 18), datetime_format)
            else:
                worksheet.set_column(i, i, max_len)

        if not df_export.empty:
            max_row, max_col = df_export.shape
            column_settings = [{'header': str(col)} for col in df_export.columns]
            worksheet.add_table(1, 0, max_row + 1, max_col - 1, {
                'columns': column_settings,
                'name': 'Atendimentos',
                'style': 'Table Style Light 1'
            })

    excel_buffer_chatwoot.seek(0)
    st.download_button(
        label=f"📥 Download da tabela Chatwoot ({total_linhas_chatwoot} linhas)",
        data=excel_buffer_chatwoot,
        file_name=f"campanhas_chatwoot_{total_linhas_chatwoot}_linhas.xlsx",
        key="download_chatwoot_escalera"
    )
    if 'andamento_atendimento' not in df_chatwoot_excel.columns:
        df_chatwoot_excel['andamento_atendimento'] = ''
    if 'termometro' not in df_chatwoot_excel.columns:
        df_chatwoot_excel['termometro'] = ''

    st.dataframe(
        df_chatwoot_excel[['conversation_id','responsavel', 'created_at', 'link_campanha', 'andamento_atendimento', 'termometro']],
        hide_index=True,
        use_container_width=True,
        column_config={
            "link_campanha": st.column_config.LinkColumn("Link Campanha", display_text="Abrir"),
            "andamento_atendimento": "Andamento Atendimento",
            "termometro": "Temperatura"
        }
    )

    st.markdown("---")

    def _transforma_descricao(val):
        if not val or not isinstance(val, str):
            return 'Nao informado'
        parts = [p.strip() for p in val.split('-')]
        if len(parts) >= 2 and parts[0].upper() == 'SN':
            return 'Seminovos'
        return parts[1] if len(parts) >= 2 else val

    def _render_graficos(df_current, df_previous, periodo_label, anterior_label):
        df_current['PERIODO_LABEL'] = periodo_label
        df_previous['PERIODO_LABEL'] = anterior_label

        df_current['DESCRICAO_PRODUTO'] = df_current['DESCRICAO_PRODUTO'].apply(_transforma_descricao)
        df_previous['DESCRICAO_PRODUTO'] = df_previous['DESCRICAO_PRODUTO'].apply(_transforma_descricao)
        df_current['MODELO'] = df_current['MODELO'].fillna('Nao informado')
        df_previous['MODELO'] = df_previous['MODELO'].fillna('Nao informado')

        df_combined = pd.concat([df_current, df_previous], ignore_index=True)

        if df_combined.empty:
            st.info("Nenhum dado encontrado para o periodo selecionado.")
            return

        st.caption(
            f"Comparativo: {periodo_label} vs mesmo periodo do mes anterior ({anterior_label})"
        )

        total_atual = len(df_current)
        total_anterior = len(df_previous)
        st.markdown(f"**Total {periodo_label}:** {total_atual} &nbsp;&nbsp;|&nbsp;&nbsp; **Total {anterior_label}:** {total_anterior}")

        col_a, col_b = st.columns(2)
        colors = ['#e63946', '#457b9d']

        with col_a:
            st.markdown("**Por Descricao do Produto**")

            df_prod = df_combined.groupby(['DESCRICAO_PRODUTO', 'PERIODO_LABEL']).size().reset_index(name='QTD')
            df_prod = df_prod.sort_values('QTD', ascending=False)

            fig_prod = px.bar(
                df_prod,
                x='DESCRICAO_PRODUTO',
                y='QTD',
                color='PERIODO_LABEL',
                barmode='group',
                color_discrete_sequence=colors[:len(df_prod['PERIODO_LABEL'].unique())],
                text_auto=True,
            )
            fig_prod.update_layout(
                xaxis_title="",
                yaxis_title="Quantidade",
                legend_title="",
                margin=dict(t=10, b=80),
                legend=dict(orientation="h", yanchor="top", y=-0.25, xanchor="center", x=0.5),
            )
            fig_prod.update_xaxes(tickangle=45)
            st.plotly_chart(fig_prod, use_container_width=True)

        with col_b:
            st.markdown("**Por Modelo**")

            df_mod = df_combined.groupby(['MODELO', 'PERIODO_LABEL']).size().reset_index(name='QTD')
            df_mod = df_mod.sort_values('QTD', ascending=False)

            fig_mod = px.bar(
                df_mod,
                x='MODELO',
                y='QTD',
                color='PERIODO_LABEL',
                barmode='group',
                color_discrete_sequence=colors[:len(df_mod['PERIODO_LABEL'].unique())],
                text_auto=True,
            )
            fig_mod.update_layout(
                xaxis_title="",
                yaxis_title="Quantidade",
                legend_title="",
                margin=dict(t=10, b=80),
                legend=dict(orientation="h", yanchor="top", y=-0.25, xanchor="center", x=0.5),
            )
            fig_mod.update_xaxes(tickangle=45)
            st.plotly_chart(fig_mod, use_container_width=True)

    def _executar_indicador(titulo, status_filter, date_col, data_inicial, data_final):
        st.subheader(titulo)

        data_inicial_anterior = data_inicial - relativedelta(months=1)
        data_final_anterior = data_final - relativedelta(months=1)

        def _build_vendas_query(data_inicial, data_final):
            return f"""
                SELECT
                    to_char(vp.COD_PROPOSTA) COD_PROPOSTA,
                    vp.EMISSAO DATA_PROPOSTA,
                    vp.data_venda,
                    pr.descricao_produto DESCRICAO_PRODUTO,
                    pm.DESCRICAO_MODELO MODELO,
                    COALESCE(ce_veic.DESCRICAO, ce_ped.DESCRICAO, ce_fic.DESCRICAO) AS COR,
                    v.CHASSI_COMPLETO,
                    c.cod_cliente CPF_CNPJ,
                    c.NOME NOME_CLIENTE,
                    CASE
                        WHEN v.novo_usado = 'U' THEN 'Usado'
                        ELSE 'Novo'
                    END NOVO_USADO,
                    CASE
                        WHEN c.COD_CID_COM IS NOT NULL THEN cid_com.DESCRICAO
                        WHEN c.COD_CID_RES IS NOT NULL THEN cid_res.DESCRICAO
                        ELSE cid_cob.DESCRICAO
                    END CIDADE_CLIENTE
                FROM VEICULOS_PROPOSTAS vP
                LEFT JOIN VEICULOS_PEDIDOS vped ON vp.COD_PEDIDO = vped.COD_PEDIDO
                LEFT JOIN PROP_FICTICIA_DADOS pfd ON vp.COD_FICTICIO = pfd.COD_FICTICIO
                LEFT JOIN caiuas_sync_rdstation csr ON csr.cod_proposta = vp.cod_proposta
                LEFT JOIN VEICULOS v ON vp.CHASSI_RESUMIDO = v.CHASSI_RESUMIDO AND vp.STATUS_PROPOSTA <> 'C'
                LEFT JOIN clientes c ON c.COD_CLIENTE = vp.COD_CLIENTE
                LEFT JOIN produtos pr ON pr.COD_PRODUTO = vp.COD_PRODUTO
                LEFT JOIN CORES_EXTERNAS ce_veic ON ce_veic.COR_EXTERNA = v.COR_EXTERNA
                LEFT JOIN CORES_EXTERNAS ce_ped ON ce_ped.COR_EXTERNA = vped.COR_EXTERNA
                LEFT JOIN CORES_EXTERNAS ce_fic ON ce_fic.COR_EXTERNA = pfd.COR_EXTERNA
                LEFT JOIN produtos_modelos pm ON pm.COD_PRODUTO = vp.COD_PRODUTO AND pm.COD_MODELO = vp.COD_MODELO
                LEFT JOIN EMPRESAS_USUARIOS eu ON eu.NOME = vp.VENDEDOR
                LEFT JOIN cidades cid_res ON cid_res.cod_cidades = c.COD_CID_RES AND cid_res.uf = c.UF_RES
                LEFT JOIN cidades cid_com ON cid_com.cod_cidades = c.COD_CID_COM AND cid_com.uf = c.UF_COM
                LEFT JOIN cidades cid_cob ON cid_cob.cod_cidades = c.COD_CID_COBRANCA AND cid_cob.uf = c.UF_COBRANCA
                WHERE {status_filter}
                    AND TRUNC({date_col}) >= TO_DATE('{data_inicial}', 'YYYY-MM-DD')
                    AND TRUNC({date_col}) <= TO_DATE('{data_final}', 'YYYY-MM-DD')
                    AND c.cod_cliente <> '22534303000127'
                ORDER BY vp.emissao
            """

        try:
            conn, cur = oracle()

            cur.execute(_build_vendas_query(data_inicial, data_final))
            result_current = cur.fetchall()
            columns = [desc[0] for desc in cur.description]

            cur.execute(_build_vendas_query(data_inicial_anterior, data_final_anterior))
            result_previous = cur.fetchall()

            cur.close()
            conn.close()

            df_current = pd.DataFrame(result_current, columns=columns) if result_current else pd.DataFrame(columns=columns)
            df_previous = pd.DataFrame(result_previous, columns=columns) if result_previous else pd.DataFrame(columns=columns)

            periodo_label = f"{data_inicial.strftime('%d/%m')} a {data_final.strftime('%d/%m')}"
            anterior_label = f"{data_inicial_anterior.strftime('%d/%m')} a {data_final_anterior.strftime('%d/%m')}"

            _render_graficos(df_current, df_previous, periodo_label, anterior_label)

        except Exception as e:
            st.error(f"Ops, falha ao consultar dados do NBS para {titulo}: {e}")

    _executar_indicador(
        "Indicador de Vendas",
        "vp.status_proposta NOT IN ('C')",
        "vp.EMISSAO",
        data_inicial_chat,
        data_final_chat,
    )

    _executar_indicador(
        "Indicador de Veiculos Faturados",
        "vp.status_proposta = 'V'",
        "vp.DATA_VENDA",
        data_inicial_chat,
        data_final_chat,
    )

