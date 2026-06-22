import io
from datetime import datetime
import streamlit as st
import pandas as pd
from database import oracle

EMAILS_ACOMPANHAMENTO_CRM = [
    "pablo.ti@caiuas.com.br",
    "marcelotcf@caiuas.com.br",
]

# Dicionário de De-Para (Nome em Maiúsculo -> Categoria)
MAPEAMENTO_EQUIPES = {
    "ALESSANDRA GABRIEL DE JESUS": "Indaiatuba",
    "FERNANDA SALLES TOLEDO CASTAGNA": "Indaiatuba",
    "GUILHERME MACHADO BAPTISTA": "Indaiatuba",
    "MARCO ANTONIO GONÇALVES": "Indaiatuba",
    "VINICIUS SCALIANTE RUFFATO": "Indaiatuba",
    "VITORIA FRANÇA DOS SANTOS": "Indaiatuba",
    "AMANDA DE OLIVEIRA JULIÓLI": "Outros",
    "DEBORA HORVATH": "Outros",
    "FABIO DE ARRUDA RAMOS": "Outros",
    "FERNANDA FRANQUIS": "Outros",
    "FRANCIELY MARCIAL DORNELAS": "Pré-atendimento",
    "STEFANY CRISTINE DE OLIVEIRA ARAUJO": "Pré-atendimento",
    "ADMILSON SERGIO DA SILVA": "Sorocaba",
    "ANDRESA APARECIDA KULLER": "Sorocaba",
    "CARLOS ALBERTO CIONE JUNIOR": "Sorocaba",
    "DANIELA RODRIGUES DA SILVA MELO": "Sorocaba",
    "DEISE MARIA GOMES DA SILVA": "Sorocaba",
    "EVERTON BRUNO DE SOUSA CAVALCANTE": "Sorocaba",
    "FELIPE FERNANDO MARIANO": "Sorocaba",
    "MATHEUS HENRIQUE SIMAS ARAUJO": "Sorocaba",
    "MATHEUS MORAES RODRIGUES": "Sorocaba"
}

def gerar_excel_detalhamento(data_ini_str, data_fin_str):
    query = f"""
        SELECT 
            TRUNC(ce.DATA_CRIACAO) AS DATA_CRIACAO,
            TRUNC(CASE
                WHEN ce.data_novo_contato IS NULL THEN ce.data_evento
                ELSE ce.data_novo_contato
            END) AS DATA_CONTATO,
            TRUNC(ce.data_agendada) AS DATA_AGENDADA,
            TRUNC(ce.data_visita) AS DATA_VISITA,
            CONCAT(ce.cod_empresa, ce.COD_EVENTO) AS EVENTO,
            CASE 
                WHEN ce.STATUS = 'D' THEN 'Descartado'
                WHEN ce.STATUS = 'E' AND ce.cod_motivo_perda IS NOT NULL THEN 'Contato perdido'
                WHEN ce.STATUS = 'E' AND ce.cod_motivo_perda IS NULL THEN 'Encerrado com sucesso'
                WHEN ce.STATUS IN ('A','P') THEN 'Aberto'
                ELSE 'Outro'
            END AS STATUS_EVENTO,
            cet.DESC_TIPO_EVENTO,
            ca.ANDAMENTO,
            ce.TERMOMETRO,
            ce.OBS_MEMO,
            cmp.desc_motivo AS MOTIVO_PERDA,
            cd.descricao_descarte AS DESCRICAO_DESCARTE,
            UPPER(eu.NOME_COMPLETO) AS RESPONSAVEL_NOME_COMPLETO,
            UPPER(eu2.NOME_COMPLETO) AS CRIOU_O_EVENTO_NOME_COMPLETO,
            pm.descricao_modelo,
            ce.COD_CLIENTE,
            CASE
                WHEN ce.COD_CLIENTE = 1 THEN ce.NOME_CLIENTE_AVULSO 
                ELSE c.NOME 
            END AS NOME_CLIENTE,
            CONCAT(c.PREFIXO_CEL, c.TELEFONE_CEL) AS TEL_CEL,
            ce.fone_cliente_avulso,
            ce.email_cliente_avulso,
            c.EMAIL_NFE,
            CONCAT(c.PREFIXO_RES, c.TELEFONE_RES) AS TEL_RESIDENCIAL,
            CONCAT(c.PREFIXO_COM, c.TELEFONE_COM) AS TEL_COMERCIAL,
            CONCAT(c.PREFIXO_FAX, c.TELEFONE_FAX) AS TEL_FAX,
            CONCAT(c.PREFIXO_MSG_TXT_INST, c.NUMERO_MSG_TXT_INST) AS TEL_WHATSAPP
        FROM crm_eventos ce
        LEFT JOIN EMPRESAS_USUARIOS eu ON eu.nome = ce.RESPONSAVEL_PELO_EVENTO
        LEFT JOIN EMPRESAS_USUARIOS eu2 ON eu2.nome = ce.CRIOU_O_EVENTO
        LEFT JOIN CRM_ANDAMENTO ca ON ca.COD_ANDAMENTO = ce.COD_ANDAMENTO
        LEFT JOIN MIDIA m ON m.COD_MIDIA = ce.COD_MIDIA 
        LEFT JOIN clientes c ON ce.COD_CLIENTE = c.COD_CLIENTE
        LEFT JOIN CRM_EVENTOS_TIPO cet ON cet.COD_TIPO_EVENTO = ce.COD_TIPO_EVENTO
        LEFT JOIN CRM_DESCARTES cd on cd.COD_DESCARTE = ce.COD_DESCARTE
        LEFT JOIN CRM_MOTIVO_PERDAS cmp ON cmp.cod_motivo_perda = ce.cod_motivo_perda
        LEFT JOIN produtos_modelos pm ON pm.COD_PRODUTO = ce.COD_PRODUTO AND pm.COD_MODELO = ce.COD_MODELO
        LEFT JOIN caiuas_crm_eventos_descartados ced ON ced.cod_empresa = ce.COD_EMPRESA AND ced.cod_evento = ce.COD_EVENTO
        WHERE 
            1=1
            AND cet.COD_TIPO_EVENTO IN (
                    829, 831, 795, 793, 797, 799, 833, 837, 819, 821, 
                    825, 785, 807, 827, 835, 815, 817, 823, 810, 812
                )
            AND TRUNC(ce.DATA_CRIACAO) >= TO_DATE('{data_ini_str}', 'YYYY-MM-DD') 
            AND TRUNC(ce.DATA_CRIACAO) <= TO_DATE('{data_fin_str}', 'YYYY-MM-DD')
    """
    
    try:
        conn, cur = oracle()
        cur.execute(query)
        rows = cur.fetchall()
        cols = [desc[0] for desc in cur.description]
        df = pd.DataFrame(rows, columns=cols)
    except Exception as e:
        st.error(f"Erro ao extrair detalhamento: {e}")
        return None
    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass

    if df.empty:
        return None

    # Tratamento das colunas de data para o Excel interpretá-las nativamente
    date_cols = ['DATA_CRIACAO', 'DATA_CONTATO', 'DATA_AGENDADA', 'DATA_VISITA']
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce').dt.date

    # Escrevendo em memória
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Detalhamento', index=False)
        workbook = writer.book
        worksheet = writer.sheets['Detalhamento']

        # Formato de data no padrão BR
        date_format = workbook.add_format({'num_format': 'dd/mm/yyyy'})

        # Identifica o tamanho da tabela
        max_row, max_col = df.shape
        
        # Insere a formatação como 'Tabela' dentro do Excel
        column_settings = [{'header': column} for column in df.columns]
        worksheet.add_table(0, 0, max_row, max_col - 1, {
            'columns': column_settings,
            'name': 'DadosGerais',
            'style': 'Table Style Medium 9'
        })

        # Rotina de redimensionamento automático de colunas
        for idx, col in enumerate(df.columns):
            # Encontra o maior comprimento entre os valores da coluna ou o próprio cabeçalho
            max_len = max(
                df[col].astype(str).map(len).max(),
                len(str(col))
            ) + 2
            
            # Aplica o formato de data caso seja uma coluna temporal
            if col in date_cols:
                worksheet.set_column(idx, idx, max_len, date_format)
            else:
                worksheet.set_column(idx, idx, max_len)

    return output.getvalue()


def render():
    # Cabeçalho da página
    st.title("📊 Acompanhamento do CRM")
    st.markdown("---")

    # 1. Filtros
    st.subheader("Filtros de Período")
    col_data_ini, col_data_fin, _ = st.columns([1, 1, 2])
    
    with col_data_ini:
        data_inicial = st.date_input("Data Inicial", datetime.now())
    with col_data_fin:
        data_final = st.date_input("Data Final", datetime.now())

    # Formatação das datas para uso nas queries
    data_ini_str = data_inicial.strftime('%Y-%m-%d')
    data_fin_str = data_final.strftime('%Y-%m-%d')

    st.markdown("---")

    # ==========================================
    # CONEXÃO COM O BANCO DE DADOS
    # ==========================================
    try:
        conn_oracle, cur_oracle = oracle()
    except Exception as e:
        st.error(f"Erro ao conectar ao banco de dados Oracle: {e}")
        return

    try:
        # ==========================================
        # VISÃO GERAL (TODOS OS EVENTOS)
        # ==========================================
        query_geral = """
            SELECT
                COUNT(CASE 
                    WHEN TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) < TRUNC(SYSDATE) 
                    THEN 1 
                END) AS ATRASADO,
                COUNT(CASE 
                    WHEN TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) = TRUNC(SYSDATE) 
                    THEN 1 
                END) AS HOJE,
                COUNT(CASE 
                    WHEN TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) > TRUNC(SYSDATE) 
                    THEN 1 
                END) AS FUTURO
            FROM
                CRM_EVENTOS ce
            LEFT JOIN CRM_EVENTOS_TIPO cet ON 1=1
                AND cet.COD_TIPO_EVENTO = ce.COD_TIPO_EVENTO
            WHERE
                1 = 1
                AND ce.STATUS IN ('P','A')
                AND cet.COD_TIPO_EVENTO IN (
                    829, 831, 795, 793, 797, 799, 833, 837, 819, 821, 
                    825, 785, 807, 827, 835, 815, 817, 823, 810, 812
                )
        """
        cur_oracle.execute(query_geral)
        row_geral = cur_oracle.fetchone()
        
        total_atrasado = int(row_geral[0] or 0)
        total_hoje = int(row_geral[1] or 0)
        total_futuro = int(row_geral[2] or 0)

        st.subheader("Quantidade de eventos criados **EM ABERTO** (Geral)")
        st.markdown("Eventos gerais que permanecem em aberto criados entre as datas selecionadas.")
        st.write("")

        col_atrasado, col_hoje, col_futuro = st.columns(3)
        with col_atrasado:
            st.metric("🔴 ATRASADO", total_atrasado)
        with col_hoje:
            st.metric("🟡 HOJE", total_hoje)
        with col_futuro:
            st.metric("🟢 FUTURO", total_futuro)

        eventos_gerais = [
            "LEAD_CHAT", "MUVECOM", "MyHonda - Automóveis - Receptivo", "MyHonda - Banco Honda - Receptivo",
            "MyHonda - Consórcio - Receptivo", "MyHonda - Outros - Receptivo", "SHOWROOM - CAMPANHAS",
            "SHOWROOM - CLIENTE OFICINA", "SHOWROOM - DES - Varejo", "SHOWROOM - DES - Venda Direta",
            "SHOWROOM - EXPOSICAO", "SHOWROOM - Fluxo de loja - Varejo", "SHOWROOM - Fluxo de loja - Venda Direta",
            "SHOWROOM - IMPLANTACAO", "SHOWROOM - Lead - Consórcio", "SHOWROOM - Lead - Varejo",
            "SHOWROOM - Lead - Venda Direta", "SHOWROOM - SHOPPING", "SHOWROOM - Telefone - Varejo",
            "SHOWROOM - Telefone - Venda Direta"
        ]

        with st.expander("Visualizar tipos de eventos analisados", expanded=False):
            st.markdown("Os seguintes tipos de eventos compõem os dados acima:")
            st.markdown("\n".join([f"- {evento}" for evento in eventos_gerais]))

        # ==========================================
        # SEÇÃO: LEADS (STORYTELLING)
        # ==========================================
        st.markdown("---")
        st.subheader("🎯 LEADS")
        st.markdown("**Quando estamos falando APENAS DE LEADS**, o cenário é esse abaixo quando selecionamos apenas os tipos de eventos:")
        
        eventos_leads = [
            "LEAD_CHAT", "MUVECOM", "MyHonda - Automóveis - Receptivo", "MyHonda - Banco Honda - Receptivo",
            "MyHonda - Consórcio - Receptivo", "MyHonda - Outros - Receptivo", "SHOWROOM - Lead - Varejo",
            "SHOWROOM - Lead - Venda Direta"
        ]
        
        st.info("\n".join([f"• {evento}" for evento in eventos_leads]))
        st.write("")

        query_leads = """
            SELECT
                COUNT(CASE 
                    WHEN TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) < TRUNC(SYSDATE) 
                    THEN 1 
                END) AS ATRASADO,
                COUNT(CASE 
                    WHEN TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) = TRUNC(SYSDATE) 
                    THEN 1 
                END) AS HOJE,
                COUNT(CASE 
                    WHEN TRUNC(CASE WHEN ce.data_novo_contato IS NULL THEN ce.data_evento ELSE ce.data_novo_contato END) > TRUNC(SYSDATE) 
                    THEN 1 
                END) AS FUTURO
            FROM
                CRM_EVENTOS ce
            LEFT JOIN CRM_EVENTOS_TIPO cet ON 1=1
                AND cet.COD_TIPO_EVENTO = ce.COD_TIPO_EVENTO
            WHERE
                1 = 1
                AND ce.STATUS IN ('P','A')
                AND cet.COD_TIPO_EVENTO IN (
                    815, 817, 829, 831, 795, 793, 797, 799, 833
                )
        """
        cur_oracle.execute(query_leads)
        row_leads = cur_oracle.fetchone()
        
        leads_atrasado = int(row_leads[0] or 0)
        leads_hoje = int(row_leads[1] or 0)
        leads_futuro = int(row_leads[2] or 0)
        
        col_leads_atrasado, col_leads_hoje, col_leads_futuro = st.columns(3)
        with col_leads_atrasado:
            st.metric("🔴 ATRASADO (Leads)", leads_atrasado)
        with col_leads_hoje:
            st.metric("🟡 HOJE (Leads)", leads_hoje)
        with col_leads_futuro:
            st.metric("🟢 FUTURO (Leads)", leads_futuro)

        # ==========================================
        # SEÇÃO: EVENTOS CRIADOS
        # ==========================================
        st.markdown("---")
        st.subheader("📅 EVENTOS CRIADOS")
        st.markdown(f"*Esses são os eventos criados entre as datas que você selecionou ({data_inicial.strftime('%d/%m/%Y')} e {data_final.strftime('%d/%m/%Y')}), AINDA ESTAMOS FALANDO SOBRE LEADS.*")
        st.write("")

        query_eventos_criados = f"""
            SELECT
                COUNT(1) AS CRIADOS_GERAL,
                COUNT(CASE WHEN ce.STATUS = 'D' THEN 1 END) AS DESCARTADOS,
                COUNT(CASE WHEN ce.STATUS = 'E' AND ce.cod_motivo_perda IS NOT NULL THEN 1 END) AS CONTATO_PERDIDO,
                COUNT(CASE WHEN ce.STATUS = 'E' AND ce.cod_motivo_perda IS NULL THEN 1 END) AS ENCERRADOS_COM_SUCESSO,
                COUNT(CASE WHEN ce.STATUS IN ('A','P') THEN 1 END) AS ABERTOS
            FROM
                CRM_EVENTOS ce
            LEFT JOIN CRM_EVENTOS_TIPO cet ON 1=1
                AND cet.COD_TIPO_EVENTO = ce.COD_TIPO_EVENTO
            WHERE
                1 = 1
                AND TRUNC(ce.DATA_CRIACAO) >= TO_DATE('{data_ini_str}', 'YYYY-MM-DD') 
                AND TRUNC(ce.DATA_CRIACAO) <= TO_DATE('{data_fin_str}', 'YYYY-MM-DD')
                AND cet.COD_TIPO_EVENTO IN (
                    815, 817, 829, 831, 795, 793, 797, 799, 833
                )
        """
        cur_oracle.execute(query_eventos_criados)
        row_criados = cur_oracle.fetchone()

        col_geral, col_descartados, col_perdidos, col_encerrados, col_abertos = st.columns(5)
        with col_geral: st.metric("📝 Geral (Criados)", int(row_criados[0] or 0))
        with col_descartados: st.metric("🗑️ Descartados", int(row_criados[1] or 0))
        with col_perdidos: st.metric("📵 Contato Perdido", int(row_criados[2] or 0))
        with col_encerrados: st.metric("✅ Encerrados", int(row_criados[3] or 0))
        with col_abertos: st.metric("📂 Ainda Abertos", int(row_criados[4] or 0))

        # ==========================================
        # SEÇÃO: COM QUEM ESTÃO OS LEADS? (APENAS ABERTOS)
        # ==========================================
        st.markdown("---")
        st.subheader("👥 Com quem estão os Leads?")
        st.markdown("Aqui visualizamos a distribuição atual de **todos os leads que ainda estão em aberto** (status Pendente ou em Andamento).")
        st.write("")

        query_atendentes = """
            SELECT
                COALESCE(UPPER(eu.NOME_COMPLETO), 'NÃO ATRIBUÍDO') AS ATENDENTE,
                COUNT(1) AS QUANTIDADE
            FROM
                CRM_EVENTOS ce
            LEFT JOIN EMPRESAS_USUARIOS eu ON eu.nome = ce.RESPONSAVEL_PELO_EVENTO
            LEFT JOIN CRM_EVENTOS_TIPO cet ON cet.COD_TIPO_EVENTO = ce.COD_TIPO_EVENTO
            WHERE
                1 = 1
                AND ce.STATUS IN ('P','A')
                AND cet.COD_TIPO_EVENTO IN (815, 817, 829, 831, 795, 793, 797, 799, 833)
            GROUP BY
                UPPER(eu.NOME_COMPLETO)
        """
        cur_oracle.execute(query_atendentes)
        rows_atendentes = cur_oracle.fetchall()
        
        def categorizar_equipe(nome):
            nome_limpo = " ".join(str(nome).split())
            return MAPEAMENTO_EQUIPES.get(nome_limpo, "Outros")

        if rows_atendentes:
            df_atendentes = pd.DataFrame(rows_atendentes, columns=['ATENDENTE', 'QUANTIDADE'])
            df_atendentes['CATEGORIA'] = df_atendentes['ATENDENTE'].apply(categorizar_equipe)

            st.markdown("### 📍 Por Unidade / Equipe")
            df_categorias = df_atendentes.groupby('CATEGORIA')['QUANTIDADE'].sum().reset_index()
            df_categorias.sort_values(by='QUANTIDADE', ascending=False, inplace=True)
            df_categorias.set_index('CATEGORIA', inplace=True)
            st.bar_chart(df_categorias, height=300)
            
            st.write("---")

            st.markdown("### 🧑‍💻 Por Atendente (Agrupado por Unidade)")
            df_atendentes.sort_values(by=['CATEGORIA', 'QUANTIDADE'], ascending=[True, False], inplace=True)
            df_grafico_individual = df_atendentes.pivot(index='ATENDENTE', columns='CATEGORIA', values='QUANTIDADE').fillna(0)
            df_grafico_individual = df_grafico_individual.reindex(df_atendentes['ATENDENTE'])
            st.bar_chart(df_grafico_individual, height=400)
        else:
            st.info("Nenhum lead em aberto encontrado.")

        # ==========================================
        # SEÇÃO: EVENTOS CRIADOS E ENVIADOS PARA OS VENDEDORES
        # ==========================================
        st.markdown("---")
        st.subheader("📤 Quantos eventos foram criados e enviados para os vendedores?")
        st.markdown(
            "Quantidade de leads criados nas datas selecionadas que estão **Em Aberto**, "
            "**Encerrados com Sucesso** ou com **Contato Perdido**. Esse gráfico foca especificamente "
            "na distribuição para as unidades de **Sorocaba** e **Indaiatuba**."
        )

        query_enviados = f"""
            SELECT
                COALESCE(UPPER(eu.NOME_COMPLETO), 'NÃO ATRIBUÍDO') AS ATENDENTE,
                COUNT(1) AS QUANTIDADE
            FROM
                CRM_EVENTOS ce
            LEFT JOIN EMPRESAS_USUARIOS eu ON eu.nome = ce.RESPONSAVEL_PELO_EVENTO
            LEFT JOIN CRM_EVENTOS_TIPO cet ON cet.COD_TIPO_EVENTO = ce.COD_TIPO_EVENTO
            WHERE
                1 = 1
                AND TRUNC(ce.DATA_CRIACAO) >= TO_DATE('{data_ini_str}', 'YYYY-MM-DD') 
                AND TRUNC(ce.DATA_CRIACAO) <= TO_DATE('{data_fin_str}', 'YYYY-MM-DD')
                AND ce.STATUS IN ('P','A','E')
                AND cet.COD_TIPO_EVENTO IN (815, 817, 829, 831, 795, 793, 797, 799, 833)
            GROUP BY
                UPPER(eu.NOME_COMPLETO)
        """
        cur_oracle.execute(query_enviados)
        rows_enviados = cur_oracle.fetchall()

        if rows_enviados:
            df_enviados = pd.DataFrame(rows_enviados, columns=['ATENDENTE', 'QUANTIDADE'])
            df_enviados['CATEGORIA'] = df_enviados['ATENDENTE'].apply(categorizar_equipe)

            qtd_outros = df_enviados[df_enviados['CATEGORIA'].isin(['Outros', 'Pré-atendimento'])]['QUANTIDADE'].sum()
            if qtd_outros > 0:
                st.warning(
                    f"⚠️ **Observação:** Existem **{qtd_outros}** eventos que foram criados e/ou transferidos "
                    f"pelo pré-atendimento (ou classificados como Outros) que **não constam** nos gráficos de Sorocaba e Indaiatuba abaixo. "
                    f"Por favor, verifique o detalhamento geral se houver divergência nos números totais."
                )
            
            st.write("")
            df_vendedores = df_enviados[df_enviados['CATEGORIA'].isin(['Sorocaba', 'Indaiatuba'])].copy()

            if not df_vendedores.empty:
                st.markdown("### 📍 Total Enviado por Empresa")
                df_empresas_enviadas = df_vendedores.groupby('CATEGORIA')['QUANTIDADE'].sum().reset_index()
                df_empresas_enviadas.set_index('CATEGORIA', inplace=True)
                st.bar_chart(df_empresas_enviadas, height=300)
                
                st.write("---")
                st.markdown("### 🧑‍💻 Enviados por Atendente (Agrupado por Unidade)")
                
                df_vendedores.sort_values(by=['CATEGORIA', 'QUANTIDADE'], ascending=[True, False], inplace=True)
                df_grafico_enviados = df_vendedores.pivot(index='ATENDENTE', columns='CATEGORIA', values='QUANTIDADE').fillna(0)
                df_grafico_enviados = df_grafico_enviados.reindex(df_vendedores['ATENDENTE'])
                
                st.bar_chart(df_grafico_enviados, height=450)
            else:
                st.info("Nenhum evento enviado para vendedores de Sorocaba ou Indaiatuba no período selecionado.")

    except Exception as e:
        st.error(f"Erro ao carregar indicadores do Oracle: {e}")
    finally:
        try:
            cur_oracle.close()
            conn_oracle.close()
        except:
            pass

    # ==========================================
    # NOVA SEÇÃO: DETALHAMENTO TOTAL (DOWNLOAD)
    # ==========================================
    st.markdown("---")
    st.subheader("📥 Detalhamento Total")
    st.markdown(
        "Faça o download da base completa de eventos gerados no período selecionado. "
        "A planilha já está formatada como tabela e com os campos de data ajustados."
    )
    
    excel_bytes = gerar_excel_detalhamento(data_ini_str, data_fin_str)
    
    if excel_bytes:
        st.download_button(
            label="📁 Baixar Planilha de Detalhamento (.xlsx)",
            data=excel_bytes,
            file_name=f"Detalhamento_CRM_{data_ini_str}_a_{data_fin_str}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("Nenhum registro encontrado para exportar no período selecionado.")