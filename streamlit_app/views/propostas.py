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

EMAILS_PRPOSTAS = [
    "pablo.ti@caiuas.com.br",
    "cristiane.aguilar@caiuas.com.br"
]


def render():
    initial_date = st.sidebar.date_input("Data Inicial", datetime.now().date(), key="prop_data_inicial")
    final_date = st.sidebar.date_input("Data Final", datetime.now().date(), key="prop_data_final")
    
    conn, cur = oracle()
    query = f"""
        SELECT 
            to_char(v.COD_PROPOSTA) COD_PROPOSTA,
            vp.EMISSAO data_proposta, 
            eu.NOME_COMPLETO nome_vendedor, 
            pm.DESCRICAO_MODELO modelo, 
            ce.DESCRICAO cor, 
            v.CHASSI_COMPLETO, 
            c.NOME nome_cliente,
            CASE 
                WHEN c.NUMERO_MSG_TXT_INST IS NOT NULL THEN c.PREFIXO_MSG_TXT_INST || c.NUMERO_MSG_TXT_INST
                WHEN c.TELEFONE_CEL IS NOT NULL THEN c.PREFIXO_CEL || c.TELEFONE_CEL
                WHEN c.TELEFONE_res IS NOT NULL THEN c.PREFIXO_RES || c.TELEFONE_res
                WHEN c.TELEFONE_COM IS NOT NULL THEN c.PREFIXO_COM || c.TELEFONE_COM
            END AS telefone,
            c.EMAIL_NFE email,
            CASE 
                WHEN v.novo_usado = 'U' THEN 'Usado'
                ELSE
                    'Novo'
            END novo_usado,
            CASE
                WHEN c.COD_CID_COM <> NULL THEN cid_com.DESCRICAO
                WHEN c.COD_CID_RES <> NULL THEN cid_res.DESCRICAO 
                ELSE cid_cob.DESCRICAO 
            END cidade,
            'Aguardando Faturamento' Status,
            concat(ce.cod_empresa, ce.COD_EVENTO) evento
        FROM veiculos v 
        LEFT JOIN produtos pr ON 1=1
            AND pr.COD_PRODUTO = v.COD_PRODUTO 
        LEFT JOIN CORES_EXTERNAS ce ON 1=1
            AND ce.COR_EXTERNA = v.COR_EXTERNA 
        LEFT JOIN produtos_modelos pm ON 1=1
            AND pm.COD_PRODUTO = v.COD_PRODUTO 
            AND pm.COD_MODELO = v.COD_MODELO 
        LEFT JOIN VEICULOS_PROPOSTAS vp ON 1=1
            --AND vp.COD_PROPOSTA = v.COD_PROPOSTA OR vp.COD_PROPOSTA = v.COD_PROPOSTA_INTERNET 
            AND vp.CHASSI_RESUMIDO = v.CHASSI_RESUMIDO 
            AND vp.STATUS_PROPOSTA <> 'C'
        LEFT JOIN clientes c ON c.COD_CLIENTE = vp.COD_CLIENTE 
        LEFT JOIN patio p ON 1=1
            AND p.COD_PATIO = v.COD_PATIO
        LEFT JOIN EMPRESAS_USUARIOS eu ON 1=1
            AND eu.NOME = vp.VENDEDOR 
        LEFT JOIN empresas_usuarios eu2 ON 1=1
            AND eu2.nome = vp.QUEM_APROVOU 
        LEFT JOIN empresas e ON 1=1
            AND e.cod_empresa = v.COD_EMPRESA 
        LEFT JOIN cidades cid_res ON 1=1
            AND cid_res.cod_cidades = c.COD_CID_RES 
            AND cid_res.uf = c.UF_RES 
        LEFT JOIN cidades cid_com ON 1=1
            AND cid_com.cod_cidades = c.COD_CID_COM 
            AND cid_com.uf = c.UF_COM 
        LEFT JOIN cidades cid_cob ON 1=1
            AND cid_cob.cod_cidades = c.COD_CID_COBRANCA  
            AND cid_cob.uf = c.UF_COBRANCA
        LEFT JOIN crm_eventos ce ON 1=1
            AND ce.COD_PROPOSTA = v.COD_PROPOSTA
            AND ce.status <> 'D'
            AND ce.cod_tipo_evento IN (829, 831,795,793,797,799,819,821,825,785,807,827,835,815,817,823,810,812)
        WHERE v.status = 'E'
            AND v.cod_proposta <> 0
            AND v.cod_proposta IS NOT NULL
        ORDER BY pm.DESCRICAO_MODELO
    """
    cur.execute(query)
    result = cur.fetchall()
    columns = [desc[0] for desc in cur.description]
    df_propostas = pd.DataFrame(result, columns=columns)
    df_propostas['DATA_PROPOSTA'] = pd.to_datetime(df_propostas['DATA_PROPOSTA'], errors='coerce').dt.strftime('%d/%m/%Y').fillna('-')
    df_propostas['EVENTO'] = df_propostas['EVENTO'].fillna('')
    df_propostas['LINK_EVENTO'] = df_propostas.apply(
        lambda row: f"https://app.caiuas.com.br/crm/eventos/{row['EVENTO']}" if row['EVENTO'] else '', axis=1
    )
    
    query = f"""
        SELECT 
            to_char(v.COD_PROPOSTA) COD_PROPOSTA, 
            vp.EMISSAO data_proposta, 
            eu.NOME_COMPLETO nome_vendedor, 
            pm.DESCRICAO_MODELO modelo, 
            ce.DESCRICAO cor, 
            v.CHASSI_COMPLETO, 
            c.NOME nome_cliente,
            CASE 
                WHEN c.NUMERO_MSG_TXT_INST IS NOT NULL THEN c.PREFIXO_MSG_TXT_INST || c.NUMERO_MSG_TXT_INST
                WHEN c.TELEFONE_CEL IS NOT NULL THEN c.PREFIXO_CEL || c.TELEFONE_CEL
                WHEN c.TELEFONE_res IS NOT NULL THEN c.PREFIXO_RES || c.TELEFONE_res
                WHEN c.TELEFONE_COM IS NOT NULL THEN c.PREFIXO_COM || c.TELEFONE_COM
            END AS telefone,
            c.EMAIL_NFE email,
            CASE 
                WHEN v.novo_usado = 'U' THEN 'Usado'
                ELSE
                    'Novo'
            END novo_usado,
            CASE
                WHEN c.COD_CID_COM <> NULL THEN cid_com.DESCRICAO
                WHEN c.COD_CID_RES <> NULL THEN cid_res.DESCRICAO 
                ELSE cid_cob.DESCRICAO 
            END cidade,
            'Faturado' Status,
            concat(ce.cod_empresa, ce.COD_EVENTO) evento
        FROM veiculos v 
        LEFT JOIN produtos pr ON 1=1
            AND pr.COD_PRODUTO = v.COD_PRODUTO 
        LEFT JOIN CORES_EXTERNAS ce ON 1=1
            AND ce.COR_EXTERNA = v.COR_EXTERNA 
        LEFT JOIN produtos_modelos pm ON 1=1
            AND pm.COD_PRODUTO = v.COD_PRODUTO 
            AND pm.COD_MODELO = v.COD_MODELO 
        LEFT JOIN VEICULOS_PROPOSTAS vp ON 1=1
            --AND vp.COD_PROPOSTA = v.COD_PROPOSTA OR vp.COD_PROPOSTA = v.COD_PROPOSTA_INTERNET 
            AND vp.CHASSI_RESUMIDO = v.CHASSI_RESUMIDO 
            AND vp.STATUS_PROPOSTA <> 'C'
        LEFT JOIN clientes c ON c.COD_CLIENTE = vp.COD_CLIENTE 
        LEFT JOIN patio p ON 1=1
            AND p.COD_PATIO = v.COD_PATIO
        LEFT JOIN EMPRESAS_USUARIOS eu ON 1=1
            AND eu.NOME = vp.VENDEDOR 
        LEFT JOIN empresas_usuarios eu2 ON 1=1
            AND eu2.nome = vp.QUEM_APROVOU 
        LEFT JOIN empresas e ON 1=1
            AND e.cod_empresa = v.COD_EMPRESA
        LEFT JOIN CLIENTES_FROTA cf ON 1=1
            AND cf.chassi = v.CHASSI_COMPLETO 
            AND cf.COD_CLIENTE = c.COD_CLIENTE  
            AND cf.nome = vp.VENDEDOR 
        LEFT JOIN cidades cid_res ON 1=1
            AND cid_res.cod_cidades = c.COD_CID_RES 
            AND cid_res.uf = c.UF_RES 
        LEFT JOIN cidades cid_com ON 1=1
            AND cid_com.cod_cidades = c.COD_CID_COM 
            AND cid_com.uf = c.UF_COM 
        LEFT JOIN cidades cid_cob ON 1=1
            AND cid_cob.cod_cidades = c.COD_CID_COBRANCA  
            AND cid_cob.uf = c.UF_COBRANCA 
        LEFT JOIN crm_eventos ce ON 1=1
            AND ce.COD_PROPOSTA = v.COD_PROPOSTA
            AND ce.status <> 'D'
            AND ce.cod_tipo_evento IN (829, 831,795,793,797,799,819,821,825,785,807,827,835,815,817,823,810,812
            )
        WHERE v.status = 'V'
            and v.cod_cliente <> '22534303000127'
            AND TRUNC(vp.EMISSAO) BETWEEN TO_DATE('{initial_date}', 'YYYY-MM-DD') AND TO_DATE('{final_date}', 'YYYY-MM-DD')
        ORDER BY pm.DESCRICAO_MODELO
    """
    cur.execute(query)
    result = cur.fetchall()
    columns = [desc[0] for desc in cur.description]
    df_faturados = pd.DataFrame(result, columns=columns)
    df_faturados['DATA_PROPOSTA'] = pd.to_datetime(df_faturados['DATA_PROPOSTA'], errors='coerce').dt.strftime('%d/%m/%Y').fillna('-')
    df_faturados['EVENTO'] = df_faturados['EVENTO'].fillna('')
    df_faturados['LINK_EVENTO'] = df_faturados.apply(
        lambda row: f"https://app.caiuas.com.br/crm/eventos/{row['EVENTO']}" if row['EVENTO'] else '', axis=1
    )
    
    query = f"""
    SELECT  
        to_char(vp.COD_PROPOSTA) COD_PROPOSTA, 
        vp.EMISSAO AS data_proposta, 
        eu.NOME_COMPLETO AS nome_vendedor, 
        pm.DESCRICAO_MODELO AS modelo, 
        cx.DESCRICAO AS cor,
        '' AS chassi_completo, 
        c.NOME AS nome_cliente,
        CASE 
            WHEN c.NUMERO_MSG_TXT_INST IS NOT NULL THEN c.PREFIXO_MSG_TXT_INST || c.NUMERO_MSG_TXT_INST
            WHEN c.TELEFONE_CEL IS NOT NULL THEN c.PREFIXO_CEL || c.TELEFONE_CEL
            WHEN c.TELEFONE_res IS NOT NULL THEN c.PREFIXO_RES || c.TELEFONE_res
            WHEN c.TELEFONE_COM IS NOT NULL THEN c.PREFIXO_COM || c.TELEFONE_COM
        END AS telefone,
        c.EMAIL_NFE AS email,
        'PEDIDO' novo_usado,
        CASE
            WHEN c.COD_CID_COM IS NOT NULL THEN cid_com.DESCRICAO
            WHEN c.COD_CID_RES IS NOT NULL THEN cid_res.DESCRICAO 
            ELSE cid_cob.DESCRICAO 
        END AS cidade,
        'Pedido' AS Status,
        concat(ev.cod_empresa, ev.COD_EVENTO) AS evento
    FROM VEICULOS_PROPOSTAS vp
    LEFT JOIN VEICULOS_PEDIDOS vped ON vped.COD_PEDIDO = vp.COD_PEDIDO
    LEFT JOIN CORES_EXTERNAS cx ON cx.COR_EXTERNA = vped.COR_EXTERNA
    LEFT JOIN produtos pr ON pr.COD_PRODUTO = vp.COD_PRODUTO 
    LEFT JOIN produtos_modelos pm ON pm.COD_PRODUTO = vp.COD_PRODUTO AND pm.COD_MODELO = vp.COD_MODELO
    LEFT JOIN clientes c ON c.COD_CLIENTE = vp.COD_CLIENTE 
    LEFT JOIN EMPRESAS_USUARIOS eu ON eu.NOME = vp.VENDEDOR 
    LEFT JOIN empresas_usuarios eu2 ON eu2.nome = vp.QUEM_APROVOU 
    LEFT JOIN empresas e ON e.cod_empresa = vp.COD_EMPRESA
    LEFT JOIN cidades cid_res ON cid_res.cod_cidades = c.COD_CID_RES AND cid_res.uf = c.UF_RES 
    LEFT JOIN cidades cid_com ON cid_com.cod_cidades = c.COD_CID_COM AND cid_com.uf = c.UF_COM 
    LEFT JOIN cidades cid_cob ON cid_cob.cod_cidades = c.COD_CID_COBRANCA AND cid_cob.uf = c.UF_COBRANCA 
    LEFT JOIN crm_eventos ev ON ev.COD_PROPOSTA = vp.COD_PROPOSTA
        AND ev.status <> 'D'
        AND ev.cod_tipo_evento IN (829, 831,795,793,797,799,819,821,825,785,807,827,835,815,817,823,810,812)
    WHERE 1=1
    AND vp.STATUS_PROPOSTA = 'A'          
    AND vp.COD_EMPRESA IN (11, 33, 111)
    AND vp.COD_PEDIDO IN (SELECT COD_PEDIDO FROM VEICULOS_PEDIDOS WHERE STATUS = 'E')
    """
    
    cur.execute(query)
    result = cur.fetchall()
    columns = [desc[0] for desc in cur.description]
    df_pedidos = pd.DataFrame(result, columns=columns)
    df_pedidos['DATA_PROPOSTA'] = pd.to_datetime(df_pedidos['DATA_PROPOSTA'], errors='coerce').dt.strftime('%d/%m/%Y').fillna('-')
    df_pedidos['EVENTO'] = df_pedidos['EVENTO'].fillna('')
    df_pedidos['LINK_EVENTO'] = df_pedidos.apply(
        lambda row: f"https://app.caiuas.com.br/crm/eventos/{row['EVENTO']}" if row['EVENTO'] else '', axis=1
    )
    
    query = f"""
        SELECT  
            to_char(vp.COD_PROPOSTA) COD_PROPOSTA, 
            vp.EMISSAO AS data_proposta, 
            eu.NOME_COMPLETO AS nome_vendedor, 
            pm.DESCRICAO_MODELO AS modelo, 
            cx.DESCRICAO AS cor,
            '' AS chassi_completo, 
            c.NOME AS nome_cliente,
            CASE 
                WHEN c.NUMERO_MSG_TXT_INST IS NOT NULL THEN c.PREFIXO_MSG_TXT_INST || c.NUMERO_MSG_TXT_INST
                WHEN c.TELEFONE_CEL IS NOT NULL THEN c.PREFIXO_CEL || c.TELEFONE_CEL
                WHEN c.TELEFONE_res IS NOT NULL THEN c.PREFIXO_RES || c.TELEFONE_res
                WHEN c.TELEFONE_COM IS NOT NULL THEN c.PREFIXO_COM || c.TELEFONE_COM
            END AS telefone,
            c.EMAIL_NFE AS email,
            'MONTADA-FLUXO' novo_usado,
            CASE
                WHEN c.COD_CID_COM IS NOT NULL THEN cid_com.DESCRICAO -- ✅ Ajustado de <> NULL para IS NOT NULL
                WHEN c.COD_CID_RES IS NOT NULL THEN cid_res.DESCRICAO 
                ELSE cid_cob.DESCRICAO 
            END AS cidade,
            'MONTADA-FLUXO' AS Status,
            concat(ev.cod_empresa, ev.COD_EVENTO) AS evento
        FROM VEICULOS_PROPOSTAS vp
        LEFT JOIN VEICULOS_PEDIDOS vped ON vped.COD_PEDIDO = vp.COD_PEDIDO
        LEFT JOIN CORES_EXTERNAS cx ON cx.COR_EXTERNA = vped.COR_EXTERNA
        LEFT JOIN produtos pr ON pr.COD_PRODUTO = vp.COD_PRODUTO 
        LEFT JOIN produtos_modelos pm ON pm.COD_PRODUTO = vp.COD_PRODUTO AND pm.COD_MODELO = vp.COD_MODELO
        LEFT JOIN clientes c ON c.COD_CLIENTE = vp.COD_CLIENTE 
        LEFT JOIN EMPRESAS_USUARIOS eu ON eu.NOME = vp.VENDEDOR 
        LEFT JOIN empresas_usuarios eu2 ON eu2.nome = vp.QUEM_APROVOU 
        LEFT JOIN empresas e ON e.cod_empresa = vp.COD_EMPRESA
        LEFT JOIN cidades cid_res ON cid_res.cod_cidades = c.COD_CID_RES AND cid_res.uf = c.UF_RES 
        LEFT JOIN cidades cid_com ON cid_com.cod_cidades = c.COD_CID_COM AND cid_com.uf = c.UF_COM 
        LEFT JOIN cidades cid_cob ON cid_cob.cod_cidades = c.COD_CID_COBRANCA AND cid_cob.uf = c.UF_COBRANCA 
        LEFT JOIN crm_eventos ev ON ev.COD_PROPOSTA = vp.COD_PROPOSTA -- ✅ Novo alias 'ev'
            AND ev.status <> 'D'
            AND ev.cod_tipo_evento IN (829, 831,795,793,797,799,819,821,825,785,807,827,835,815,817,823,810,812)
        WHERE 1=1
        and nvl(vp.cod_ficticio,0) > 0
        AND vp.STATUS_PROPOSTA = 'A'
        and nvl(vp.internet,'N')  <> 'I'
        and nvl(vp.internet,'N')  <> 'F'
        and nvl(vp.tipo_montada,'F')  = 'F'
    """
    cur.execute(query)
    result = cur.fetchall()
    columns = [desc[0] for desc in cur.description]
    df_montada_fluxo = pd.DataFrame(result, columns=columns)
    df_montada_fluxo['DATA_PROPOSTA'] = pd.to_datetime(df_montada_fluxo['DATA_PROPOSTA'], errors='coerce').dt.strftime('%d/%m/%Y').fillna('-')
    df_montada_fluxo['EVENTO'] = df_montada_fluxo['EVENTO'].fillna('')
    df_montada_fluxo['LINK_EVENTO'] = df_montada_fluxo.apply(
        lambda row: f"https://app.caiuas.com.br/crm/eventos/{row['EVENTO']}" if row['EVENTO'] else '', axis =1
    )
    
    query = f"""
        SELECT DISTINCT 
            to_char(vp.COD_PROPOSTA) AS COD_PROPOSTA,
            vp.EMISSAO AS data_proposta, 
            eu.NOME_COMPLETO AS nome_vendedor, 
            pm.DESCRICAO_MODELO AS modelo, 
            cx.DESCRICAO AS cor,
            '' AS chassi_completo, 
            c.NOME AS nome_cliente,
            CASE 
                WHEN c.NUMERO_MSG_TXT_INST IS NOT NULL THEN c.PREFIXO_MSG_TXT_INST || c.NUMERO_MSG_TXT_INST
                WHEN c.TELEFONE_CEL IS NOT NULL THEN c.PREFIXO_CEL || c.TELEFONE_CEL
                WHEN c.TELEFONE_res IS NOT NULL THEN c.PREFIXO_RES || c.TELEFONE_res
                WHEN c.TELEFONE_COM IS NOT NULL THEN c.PREFIXO_COM || c.TELEFONE_COM
            END AS telefone,
            c.EMAIL_NFE AS email,
            'MONTADA-PEDIDO' novo_usado,
            CASE
                WHEN c.COD_CID_COM IS NOT NULL THEN cid_com.DESCRICAO 
                WHEN c.COD_CID_RES IS NOT NULL THEN cid_res.DESCRICAO 
                ELSE cid_cob.DESCRICAO 
            END AS cidade,
            'Montada-Pedido' AS Status,
            concat(ev.cod_empresa, ev.COD_EVENTO) AS evento
        FROM VEICULOS_PROPOSTAS vp
        LEFT JOIN PROP_FICTICIA_DADOS pfd ON pfd.COD_FICTICIO = vp.COD_FICTICIO
        LEFT JOIN CORES_EXTERNAS cx ON cx.COR_EXTERNA = pfd.COR_EXTERNA
        INNER JOIN produtos pr ON pr.COD_PRODUTO = vp.COD_PRODUTO 
        INNER JOIN produtos_modelos pm ON pm.COD_PRODUTO = vp.COD_PRODUTO AND pm.COD_MODELO = vp.COD_MODELO
        INNER JOIN clientes c ON c.COD_CLIENTE = vp.COD_CLIENTE 
        INNER JOIN cliente_diverso cd ON cd.COD_CLIENTE = c.COD_CLIENTE 
        LEFT JOIN EMPRESAS_USUARIOS eu ON eu.NOME = vp.VENDEDOR 
        LEFT JOIN empresas_usuarios eu2 ON eu2.nome = vp.QUEM_APROVOU 
        LEFT JOIN empresas e ON e.cod_empresa = vp.COD_EMPRESA
        LEFT JOIN cidades cid_res ON cid_res.cod_cidades = c.COD_CID_RES AND cid_res.uf = c.UF_RES 
        LEFT JOIN cidades cid_com ON cid_com.cod_cidades = c.COD_CID_COM AND cid_com.uf = c.UF_COM 
        LEFT JOIN cidades cid_cob ON cid_cob.cod_cidades = c.COD_CID_COBRANCA AND cid_cob.uf = c.UF_COBRANCA 
        LEFT JOIN crm_eventos ev ON ev.COD_PROPOSTA = vp.COD_PROPOSTA 
            AND ev.status <> 'D'
            AND ev.cod_tipo_evento IN (829, 831,795,793,797,799,819,821,825,785,807,827,835,815,817,823,810,812)
        WHERE 1=1
            AND vp.STATUS_PROPOSTA = 'A'
            AND vp.COD_EMPRESA IN (11,33)
            AND vp.VENDEDOR IN (
                SELECT a.nome
                FROM empresas_usuarios a
                INNER JOIN empresas b ON a.cod_empresa = b.cod_empresa
                INNER JOIN gp_veiculo_empresa c ON c.cod_empresa = b.cod_empresa
                WHERE c.cod_grupo = 1
            )
            AND vp.COD_EMPRESA IN (
                SELECT a.cod_empresa 
                FROM gp_veiculo_empresa a
                INNER JOIN regiao_veiculo_grupo b ON a.cod_grupo = b.cod_grupo 
                WHERE b.cod_regiao = 1
            ) 
            AND NVL(vp.COD_FICTICIO, 0) > 0
            AND NVL(vp.INTERNET, 'N') <> 'I'
            AND NVL(vp.INTERNET, 'N') <> 'F'
            AND NVL(vp.TIPO_MONTADA, 'F') = 'P'
        ORDER BY 2
    """
    cur.execute(query)
    result = cur.fetchall()
    columns = [desc[0] for desc in cur.description]
    df_montada_pedido = pd.DataFrame(result, columns=columns)
    df_montada_pedido['DATA_PROPOSTA'] = pd.to_datetime(df_montada_pedido['DATA_PROPOSTA'], errors='coerce').dt.strftime('%d/%m/%Y').fillna('-')
    df_montada_pedido['EVENTO'] = df_montada_pedido['EVENTO'].fillna('')
    df_montada_pedido['LINK_EVENTO'] = df_montada_pedido.apply(
        lambda row: f"https://app.caiuas.com.br/crm/eventos/{row['EVENTO']}" if row['EVENTO'] else '', axis=1
    )
    
    query = f"""
        SELECT DISTINCT 
            to_char(vp.COD_PROPOSTA) AS COD_PROPOSTA, 
            vp.EMISSAO AS data_proposta, 
            eu.NOME_COMPLETO AS nome_vendedor, 
            pm.DESCRICAO_MODELO AS modelo, 
            cx.DESCRICAO AS cor, 
            '' AS chassi_completo, 
            c.NOME AS nome_cliente,
            CASE 
                WHEN c.NUMERO_MSG_TXT_INST IS NOT NULL THEN c.PREFIXO_MSG_TXT_INST || c.NUMERO_MSG_TXT_INST
                WHEN c.TELEFONE_CEL IS NOT NULL THEN c.PREFIXO_CEL || c.TELEFONE_CEL
                WHEN c.TELEFONE_res IS NOT NULL THEN c.PREFIXO_RES || c.TELEFONE_res
                WHEN c.TELEFONE_COM IS NOT NULL THEN c.PREFIXO_COM || c.TELEFONE_COM
            END AS telefone,
            c.EMAIL_NFE AS email,
            'Frotista' AS novo_usado,
            CASE
                WHEN c.COD_CID_COM IS NOT NULL THEN cid_com.DESCRICAO 
                WHEN c.COD_CID_RES IS NOT NULL THEN cid_res.DESCRICAO 
                ELSE cid_cob.DESCRICAO 
            END AS cidade,
            'Frotista' AS Status,
            concat(ev.cod_empresa, ev.COD_EVENTO) AS evento
        FROM VEICULOS_PROPOSTAS vp
        INNER JOIN produtos pr ON pr.COD_PRODUTO = vp.COD_PRODUTO 
        INNER JOIN produtos_modelos pm ON pm.COD_PRODUTO = vp.COD_PRODUTO AND pm.COD_MODELO = vp.COD_MODELO
        LEFT JOIN clientes c ON c.COD_CLIENTE = vp.COD_CLIENTE 
        LEFT JOIN PROP_FICTICIA_DADOS pfd ON pfd.COD_FICTICIO = vp.COD_FICTICIO
        LEFT JOIN CORES_EXTERNAS cx ON cx.COR_EXTERNA = pfd.COR_EXTERNA
        LEFT JOIN EMPRESAS_USUARIOS eu ON eu.NOME = vp.VENDEDOR 
        LEFT JOIN cidades cid_res ON cid_res.cod_cidades = c.COD_CID_RES AND cid_res.uf = c.UF_RES 
        LEFT JOIN cidades cid_com ON cid_com.cod_cidades = c.COD_CID_COM AND cid_com.uf = c.UF_COM 
        LEFT JOIN cidades cid_cob ON cid_cob.cod_cidades = c.COD_CID_COBRANCA AND cid_cob.uf = c.UF_COBRANCA 
        LEFT JOIN crm_eventos ev ON ev.COD_PROPOSTA = vp.COD_PROPOSTA 
            AND ev.status <> 'D'
            AND ev.cod_tipo_evento IN (829, 831,795,793,797,799,819,821,825,785,807,827,835,815,817,823,810,812)
        WHERE 1=1
            AND vp.STATUS_PROPOSTA = 'A'
            AND vp.INTERNET = 'F'
    """
    cur.execute(query)
    result = cur.fetchall()
    columns = [desc[0] for desc in cur.description]
    df_frotista = pd.DataFrame(result, columns=columns)
    df_frotista['DATA_PROPOSTA'] = pd.to_datetime(df_frotista['DATA_PROPOSTA'], errors='coerce').dt.strftime('%d/%m/%Y').fillna('-')
    df_frotista['EVENTO'] = df_frotista['EVENTO'].fillna('')
    df_frotista['LINK_EVENTO'] = df_frotista.apply(
        lambda row: f"https://app.caiuas.com.br/crm/eventos/{row['EVENTO']}" if row['EVENTO'] else '', axis=1
    )
    
    ndf = pd.concat([df_propostas, df_faturados, df_pedidos, df_montada_fluxo, df_montada_pedido, df_frotista], ignore_index=True)
    ndf = ndf.sort_values(by='DATA_PROPOSTA', key=lambda x: pd.to_datetime(x, format='%d/%m/%Y', errors='coerce'), ascending=True)
    # replace none to ''
    ndf = ndf.fillna('')
    
    # fechando conexão
    cur.close()
    conn.close()
    
    ndf_download = ndf.rename(columns={
        'COD_PROPOSTA': 'Proposta',
        'DATA_PROPOSTA': 'Data Proposta',
        'NOME_VENDEDOR': 'Vendedor',
        'MODELO': 'Modelo',
        'COR': 'Cor',
        'CHASSI_COMPLETO': 'Chassi',
        'NOME_CLIENTE': 'Cliente',
        'NOVO_USADO': 'Novo/Usado',
        'CIDADE': 'Cidade',
        'STATUS': 'Status',
        'LINK_EVENTO': 'Evento NBS'
    })
    import io
    from openpyxl import load_workbook
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.table import Table, TableStyleInfo
    
    _xlsx_buffer = io.BytesIO()
    ndf_download.to_excel(_xlsx_buffer, index=False, engine='openpyxl')
    _xlsx_buffer.seek(0)
    
    wb = load_workbook(_xlsx_buffer)
    ws = wb.active
    
    # Formatar coluna "Data Proposta" como data real no Excel
    from datetime import datetime as _dt
    date_col_idx = None
    for idx, cell in enumerate(ws[1], start=1):
        if cell.value == 'Data Proposta':
            date_col_idx = idx
            break
    if date_col_idx:
        for row in ws.iter_rows(min_row=2, min_col=date_col_idx, max_col=date_col_idx):
            for cell in row:
                if cell.value and cell.value != '-':
                    try:
                        cell.value = _dt.strptime(str(cell.value), '%d/%m/%Y')
                        cell.number_format = 'DD/MM/YYYY'
                    except ValueError:
                        pass
    
    # Criar tabela nomeada "Propostas"
    max_row = ws.max_row
    max_col = ws.max_column
    table_ref = f"A1:{get_column_letter(max_col)}{max_row}"
    table = Table(displayName="Propostas", ref=table_ref)
    table.tableStyleInfo = TableStyleInfo(name="TableStyleMedium9", showFirstColumn=False,
                                          showLastColumn=False, showRowStripes=True, showColumnStripes=False)
    ws.add_table(table)
    
    # Redimensionar largura das colunas automaticamente
    for col in ws.columns:
        max_len = max((len(str(cell.value)) if cell.value is not None else 0) for cell in col)
        ws.column_dimensions[get_column_letter(col[0].column)].width = min(max_len + 4, 60)
    
    _xlsx_buffer = io.BytesIO()
    wb.save(_xlsx_buffer)
    _xlsx_buffer.seek(0)
    
    st.download_button(
        label="📥 Baixar planilha",
        data=_xlsx_buffer,
        file_name="propostas.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    
    st.dataframe(
        ndf_download,
        hide_index=True,
        use_container_width=True,
        height=800,
        column_config={
            "Evento NBS": st.column_config.LinkColumn("Evento NBS", display_text="Abrir"),
        }
    )
    
    
    
    