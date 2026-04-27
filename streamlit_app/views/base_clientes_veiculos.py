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

EMAILS_BASE_CLIENTES = [
    "pablo.ti@caiuas.com.br",
]


def render():
    st.title("Consulta Base Unificada de Clientes e Veículos")
    
    # Buscar produtos para o filtro
    try:
        conn_pm, cur_pm = oracle()
        cur_pm.execute("""
            SELECT DISTINCT p.COD_PRODUTO, p.DESCRICAO_PRODUTO  
            FROM produtos p
            WHERE p.COD_PRODUTO IN (SELECT DISTINCT COD_PRODUTO FROM produtos_modelos)
            ORDER BY p.DESCRICAO_PRODUTO
        """)
        produtos_result = cur_pm.fetchall()
        produtos_opcoes = {row[1]: row[0] for row in produtos_result}
        cur_pm.close()
        conn_pm.close()
    except Exception as e:
        st.error(f"Erro ao carregar produtos: {e}")
        produtos_opcoes = {}
    
    # Filtros na sidebar
    st.sidebar.subheader("Filtros")
    filtro_chassi = st.sidebar.text_input("Chassi", placeholder="Digite o chassi completo...")
    
    # Multiselect para produtos
    produtos_selecionados = st.sidebar.multiselect(
        "Produtos",
        options=list(produtos_opcoes.keys()),
        placeholder="Selecione os produtos..."
    )
    
    # Buscar modelos baseado nos produtos selecionados (via query SQL)
    modelos_opcoes = {}
    if produtos_selecionados:
        try:
            codigos_produtos = [str(produtos_opcoes[p]) for p in produtos_selecionados]
            conn_mod, cur_mod = oracle()
            cur_mod.execute(f"""
                SELECT DISTINCT pm.COD_MODELO, pm.DESCRICAO_MODELO  
                FROM produtos_modelos pm
                WHERE pm.COD_PRODUTO IN ({','.join(codigos_produtos)})
                ORDER BY pm.DESCRICAO_MODELO
            """)
            modelos_result = cur_mod.fetchall()
            modelos_opcoes = {row[1]: row[0] for row in modelos_result if row[1]}
            cur_mod.close()
            conn_mod.close()
        except Exception as e:
            st.error(f"Erro ao carregar modelos: {e}")
    else:
        # Se nenhum produto selecionado, carregar todos os modelos
        try:
            conn_mod, cur_mod = oracle()
            cur_mod.execute("""
                SELECT DISTINCT pm.COD_MODELO, pm.DESCRICAO_MODELO  
                FROM produtos_modelos pm
                WHERE pm.DESCRICAO_MODELO IS NOT NULL
                ORDER BY pm.DESCRICAO_MODELO
            """)
            modelos_result = cur_mod.fetchall()
            modelos_opcoes = {row[1]: row[0] for row in modelos_result if row[1]}
            cur_mod.close()
            conn_mod.close()
        except Exception as e:
            st.error(f"Erro ao carregar modelos: {e}")
    
    # Multiselect para modelos
    modelos_selecionados = st.sidebar.multiselect(
        "Modelos",
        options=list(modelos_opcoes.keys()),
        placeholder="Selecione os modelos..."
    )
    
    # Buscar anos disponíveis na base
    anos_opcoes = []
    try:
        conn_ano, cur_ano = oracle()
        cur_ano.execute("""
            SELECT DISTINCT ANO FROM (
                SELECT DISTINCT TO_CHAR(ANO) AS ANO FROM OS_DADOS_VEICULOS WHERE ANO IS NOT NULL
                UNION
                SELECT DISTINCT TO_CHAR(ANO) AS ANO FROM clientes_frota WHERE ANO IS NOT NULL
                UNION
                SELECT DISTINCT TO_CHAR(ANO_MODELO) AS ANO FROM VEICULOS WHERE ANO_MODELO IS NOT NULL
            )
            ORDER BY ANO DESC
        """)
        anos_result = cur_ano.fetchall()
        anos_opcoes = [str(row[0]).strip() for row in anos_result if row[0] and str(row[0]).strip()]
        cur_ano.close()
        conn_ano.close()
    except Exception as e:
        st.error(f"Erro ao carregar anos: {e}")
    
    # Multiselect para anos
    anos_selecionados = st.sidebar.multiselect(
        "Ano do Veículo",
        options=anos_opcoes,
        placeholder="Selecione os anos..."
    )
    
    filtro_vendido = st.sidebar.selectbox("Status Vendido", ["Todos", "Vendido", "Não Vendido"])
    filtro_tipo_doc = st.sidebar.selectbox("Tipo de Cliente", ["Todos", "CPF", "CNPJ"])
    filtro_uf = st.sidebar.text_input("UF", placeholder="Ex: SP, RJ, MG...")
    filtro_cidade = st.sidebar.text_input("Cidade", placeholder="Digite o nome da cidade...")
    
    # Construção dinâmica dos filtros SQL
    filtros_sql = []
    if filtro_chassi:
        filtros_sql.append(f"AND CHASSI = '{filtro_chassi.strip()}'")
    if produtos_selecionados:
        codigos_produtos = [str(produtos_opcoes[p]) for p in produtos_selecionados]
        filtros_sql.append(f"AND COD_PRODUTO IN ({','.join(codigos_produtos)})")
    if modelos_selecionados:
        codigos_modelos = [str(modelos_opcoes[m]) for m in modelos_selecionados]
        filtros_sql.append(f"AND COD_MODELO IN ({','.join(codigos_modelos)})")
    if anos_selecionados:
        anos_str = ','.join([f"'{a}'" for a in anos_selecionados])
        filtros_sql.append(f"AND TO_CHAR(ANO) IN ({anos_str})")
    if filtro_vendido == "Vendido":
        filtros_sql.append("AND VENDIDO = 'S'")
    elif filtro_vendido == "Não Vendido":
        filtros_sql.append("AND (VENDIDO IS NULL OR VENDIDO = 'N')")
    if filtro_tipo_doc == "CPF":
        filtros_sql.append("AND LENGTH(TO_CHAR(COD_CLIENTE)) <= 11")
    elif filtro_tipo_doc == "CNPJ":
        filtros_sql.append("AND LENGTH(TO_CHAR(COD_CLIENTE)) > 11")
    if filtro_uf:
        filtros_sql.append(f"AND ENDERECO_UF = '{filtro_uf.strip().upper()}'")
    if filtro_cidade:
        filtros_sql.append(f"AND upper(ENDERECO_CIDADE) = upper('{filtro_cidade.strip()}')")
    
    filtros_where = " ".join(filtros_sql)
    
    query = f"""
    WITH base_unificada AS (
        -- 1. Dados de Oficina
        SELECT 
            os.COD_CLIENTE, 
            odv.CHASSI, 
            odv.COD_PRODUTO, 
            odv.COD_MODELO, 
            odv.ANO,
            MAX(os.data_emissao) AS ultima_passagem_oficina,
            CAST(NULL AS NUMBER) AS KM,
            CAST(NULL AS VARCHAR2(20)) AS PLACA,
            CAST(NULL AS VARCHAR2(1)) AS VENDIDO
        FROM OS_DADOS_VEICULOS odv 
        INNER JOIN os os 
            ON os.NUMERO_OS = odv.NUMERO_OS 
            AND os.COD_EMPRESA = odv.COD_EMPRESA 
        WHERE os.COD_EMPRESA IN (11, 33)
        GROUP BY
            os.COD_CLIENTE,
            odv.CHASSI, 
            odv.COD_PRODUTO, 
            odv.COD_MODELO, 
            odv.ANO
        UNION ALL
        -- 2. Dados de Clientes Frota
        SELECT 
            cf.COD_CLIENTE,
            cf.CHASSI, 
            cf.COD_PRODUTO, 
            cf.COD_MODELO, 
            cf.ANO,
            CAST(NULL AS DATE) AS ultima_passagem_oficina,
            cf.KM,
            cf.PLACA,
            cf.VENDIDO 
        FROM clientes_frota cf
        UNION ALL
        -- 3. Dados de Veículos
        SELECT 
            v.COD_CLIENTE,
            v.CHASSI_COMPLETO AS CHASSI, 
            v.COD_PRODUTO, 
            v.COD_MODELO, 
            v.ANO_MODELO AS ANO,
            CAST(NULL AS DATE) AS ultima_passagem_oficina,
            CAST(NULL AS NUMBER) AS KM,
            CAST(NULL AS VARCHAR2(20)) AS PLACA,
            CAST(NULL AS VARCHAR2(1)) AS VENDIDO
        FROM VEICULOS v 
        WHERE v.COD_EMPRESA IN (11, 33, 111)
    ),
    -- Agrupa tudo por CLIENTE e CHASSI para matar a duplicidade
    dados_agrupados AS (
        SELECT 
            COD_CLIENTE,
            CHASSI,
            MAX(COD_PRODUTO) AS COD_PRODUTO,
            MAX(COD_MODELO) AS COD_MODELO,
            MAX(ANO) AS ANO,
            MAX(ultima_passagem_oficina) AS ultima_passagem_oficina,
            MAX(KM) AS KM,
            MAX(PLACA) AS PLACA,
            MAX(VENDIDO) AS VENDIDO
        FROM base_unificada
        GROUP BY 
            COD_CLIENTE,
            CHASSI
    ),
    -- Consolida os dados e aplica a regra de prioridade de endereço
    dados_completos AS (
        SELECT 
            da.COD_CLIENTE, 
            c.NOME, 
            c.EMAIL_NFE,
            REGEXP_REPLACE(concat(c.PREFIXO_CEL, c.TELEFONE_CEL), '[^0-9]', '') AS tel_cel,
            REGEXP_REPLACE(concat(c.PREFIXO_RES, c.TELEFONE_RES), '[^0-9]', '') AS tel_residencial,
            REGEXP_REPLACE(concat(c.PREFIXO_COM, c.TELEFONE_COM), '[^0-9]', '') AS tel_comercial,
            REGEXP_REPLACE(concat(c.PREFIXO_FAX, c.TELEFONE_FAX), '[^0-9]', '') AS tel_fax,
            REGEXP_REPLACE(concat(c.PREFIXO_MSG_TXT_INST, c.NUMERO_MSG_TXT_INST), '[^0-9]', '') AS tel_whatsapp,
            -- Aplicação do COALESCE para prioridade de endereço (Residencial > Comercial > Cobrança)
            COALESCE(c.RUA_RES, c.RUA_COM, c.RUA_COBRANCA) AS ENDERECO_RUA,
            COALESCE(c.BAIRRO_RES, c.BAIRRO_COM, c.BAIRRO_COBRANCA) AS ENDERECO_BAIRRO,
            COALESCE(c.COMPLEMENTO_RES, c.COMPLEMENTO_COM, c.COMPLEMENTO_COBRANCA) AS ENDERECO_COMPLEMENTO,
            COALESCE(c.CEP_RES, c.CEP_COM, c.CEP_COBRANCA) AS ENDERECO_CEP,
            COALESCE(cir.DESCRICAO, cicom.DESCRICAO, cicob.DESCRICAO) AS ENDERECO_CIDADE,
            COALESCE(cir.UF, cicom.UF, cicob.UF) AS ENDERECO_UF,
            da.CHASSI, 
            da.COD_PRODUTO, 
            p.descricao_produto, 
            da.COD_MODELO, 
            pm.DESCRICAO_MODELO, 
            da.ANO,
            da.ultima_passagem_oficina,
            da.KM,
            da.PLACA,
            da.VENDIDO
        FROM dados_agrupados da
        LEFT JOIN produtos p ON 1=1
            AND p.COD_PRODUTO = da.COD_PRODUTO
        LEFT JOIN PRODUTOS_MODELOS pm ON 1=1
            AND pm.COD_MODELO = da.COD_MODELO
            AND pm.COD_PRODUTO = da.COD_PRODUTO 
        LEFT JOIN clientes c ON 1=1
            AND c.COD_CLIENTE = da.COD_CLIENTE 
        LEFT JOIN cidades cir ON 1=1
            AND cir.COD_CIDADES = c.COD_CID_RES
        LEFT JOIN cidades cicom ON 1=1
            AND cicom.COD_CIDADES = c.COD_CID_COM
        LEFT JOIN cidades cicob ON 1=1
            AND cicob.COD_CIDADES = c.COD_CID_COBRANCA
    )
    -- Consulta final já permitindo os filtros limpos
    SELECT * FROM dados_completos
    WHERE 1=1
        {filtros_where}
    """
    
    # Verifica se algum filtro foi aplicado
    if not filtros_sql:
        st.warning("⚠️ Por favor, aplique pelo menos um filtro para realizar a consulta. A base completa é muito grande.")
    else:
        try:
            conn_oracle, cur_oracle = oracle()
            cur_oracle.execute(query)
            result_oracle = cur_oracle.fetchall()
            columns = [desc[0] for desc in cur_oracle.description]
            df = pd.DataFrame(result_oracle, columns=columns)
            cur_oracle.close()
            conn_oracle.close()
            
            if df.empty:
                st.info("Nenhum registro encontrado com os filtros aplicados.")
            else:
                # Formatar data se houver
                if 'ULTIMA_PASSAGEM_OFICINA' in df.columns:
                    df['ULTIMA_PASSAGEM_OFICINA'] = pd.to_datetime(df['ULTIMA_PASSAGEM_OFICINA'], errors='coerce')
                    df['ULTIMA_PASSAGEM_OFICINA'] = df['ULTIMA_PASSAGEM_OFICINA'].dt.strftime('%d/%m/%Y').fillna('-')
                
                # Substituir NaN por '-'
                df = df.fillna('-')
                
                st.write(f"**Total de registros encontrados: {len(df)}**")
                st.write(f"**Data de atualização: {datetime.now().strftime('%d/%m/%Y %H:%M')}**")
                
                # Botão de download
                excel_buffer = io.BytesIO()
                df.to_excel(excel_buffer, index=False, sheet_name="Base Clientes Veículos")
                excel_buffer.seek(0)
                st.download_button(
                    label="📥 Download da planilha (Excel)",
                    data=excel_buffer,
                    file_name="base_clientes_veiculos.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
                # Exibir tabela
                st.dataframe(df, hide_index=True, use_container_width=True)
                
        except Exception as e:
            st.error(f"Erro ao executar a consulta: {e}")
    