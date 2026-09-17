import os
import logging
import datetime
import requests
import json
from io import BytesIO
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.gridspec import GridSpec
import numpy as np
from app import app
from database import oracle

logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT", "")
TELEGRAM_CHATS = {
    "Pablo": "548519349",
    "Cristiane": "8703967479",
    "Marcelo Camargo": "8105764200",
}
LOGO_PATH = "images/logo_honda.png"
now = datetime.datetime.now()

if now.weekday() == 0:
    initial_date = now - datetime.timedelta(days=2)
else:
    initial_date = now - datetime.timedelta(days=1)

query = f"""
SELECT
	CASE
    	WHEN es.descricao_sala = 'Caiuas Indaiatuba-Novos/Usados' THEN 'INDMAR'
    	ELSE 'CAMARGO - SOROCABA'
    END cf_nome_da_empresa,
    c.NOME nome_cliente,
    eu.NOME_COMPLETO cf_consultor,
    c.EMAIL_NFE email,
    concat(concat(pm.DESCRICAO_MODELO, ' - '),v.ANO_MODELO) cf_modelo_do_carro,
    v.ANO_MODELO cf_ano_veiculo,
    CASE
        WHEN v.novo_usado = 'U' THEN 'Usado'
        WHEN v.COD_PROPOSTA_INTERNET IS NOT NULL OR vp.INTERNET = 'F' THEN 'Direta'
        ELSE
            'Novo'
    END cf_tipo_veiculo
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
LEFT JOIN ev_agendados ea ON 1=1
	AND ea.STATUS NOT IN ('C')
        AND TO_CHAR(ea.COD_PROPOSTA) = TO_CHAR(vp.COD_PROPOSTA)
        AND TO_CHAR(ea.CHASSI_RESUMIDO) = TO_CHAR(v.CHASSI_RESUMIDO)
    left join EV_SALAS es on 1=1
        and es.cod_sala = ea.cod_sala
    left join caiuas_veic_proc cvp on 1=1
        and cvp.cod_proposta = vp.cod_proposta
    LEFT JOIN caiuas_recebimento_veiculo crv ON 1=1
        AND crv.cod_modelo = v.COD_MODELO
        AND crv.cod_produto = v.COD_PRODUTO
        AND crv.chassi_resumido = v.CHASSI_RESUMIDO
        AND crv.cod_empresa = v.COD_EMPRESA
   where 1=1
   		AND TRUNC(ea.DATA_BAIXA) >= TO_DATE('{initial_date.strftime("%Y-%m-%d")}', 'YYYY-MM-DD')
   		AND TRUNC(ea.DATA_BAIXA) <= TO_DATE('{now.strftime("%Y-%m-%d")}', 'YYYY-MM-DD')
 """


conn, cur = oracle()
cur.execute(query)
result = cur.fetchall()
columns = [desc[0] for desc in cur.description]
df = pd.DataFrame(result, columns=columns)

df_email = df.copy()
# padroniza Nome/Email a partir das colunas da consulta de veiculos entregues
if 'NOME_CLIENTE' in df_email.columns:
    df_email = df_email.rename(columns={'NOME_CLIENTE': 'Nome'})
if 'EMAIL' in df_email.columns:
    df_email = df_email.rename(columns={'EMAIL': 'Email'})
df_email = df_email.drop_duplicates().reset_index(drop=True)
df_email = df_email[df_email['Email'].notna() & (df_email['Email'] != '')]
# reduz rejeicoes 400 por email malformado
df_email = df_email[df_email['Email'].str.contains(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", na=False)]

# gera um df com todos os contatos que não tem email nenhum
leads_sem_email = df[df['EMAIL'].isna() | (df['EMAIL'] == '')].reset_index(drop=True)

url = "https://api.rd.services/auth/token"
payload = json.dumps({
  "client_id": os.getenv("RDSTATION_CLIENT_ID_CAIUAS", ""),
  "client_secret": os.getenv("RDSTATION_CLIENT_SECRET_CAIUAS", ""),
  "refresh_token": os.getenv("RDSTATION_REFRESH_TOKEN_CAIUAS", "")
})
access_token = None
try:
    response = requests.request("POST", url, headers={"Content-Type": "application/json"}, data=payload)
    response.raise_for_status()
    access_token = response.json().get("access_token")
except requests.exceptions.RequestException as e:
    logger.error("Erro ao obter access token do RD Station: %s", e)

df_email['COD_RDSTATION'] = None


def _safe_str(value):
    if pd.isna(value):
        return ""
    return str(value)


def _format_sheet_as_table(writer, dataframe, sheet_name):
    worksheet = writer.sheets[sheet_name]
    n_rows, n_cols = dataframe.shape

    if n_cols == 0:
        return

    header_format = writer.book.add_format({"bold": True})
    worksheet.set_row(0, None, header_format)

    # Inclui ao menos a linha de cabecalho na tabela.
    last_row = max(n_rows, 1)
    worksheet.add_table(
        0,
        0,
        last_row,
        n_cols - 1,
        {
            "name": f"tbl_{sheet_name.replace(' ', '_')[:20]}",
            "style": "Table Style Medium 9",
            "columns": [{"header": str(col)} for col in dataframe.columns],
        },
    )

    for col_idx, col_name in enumerate(dataframe.columns):
        serie = dataframe[col_name].fillna("").astype(str)
        max_data_len = serie.map(len).max() if not serie.empty else 0
        max_len = max(len(str(col_name)), max_data_len)
        worksheet.set_column(col_idx, col_idx, min(max_len + 2, 60))


if access_token:
    for _, linha in df_email.iterrows():
        url = "https://api.rd.services/platform/events?event_type=conversion"
        nome = _safe_str(linha.get('Nome'))
        email = _safe_str(linha.get('Email'))
        empresa = _safe_str(linha.get('CF_NOME_DA_EMPRESA'))
        consultor = _safe_str(linha.get('CF_CONSULTOR'))
        modelo_carro = _safe_str(linha.get('CF_MODELO_DO_CARRO'))
        ano_veiculo = _safe_str(linha.get('CF_ANO_VEICULO'))
        tipo_veiculo = _safe_str(linha.get('CF_TIPO_VEICULO'))
        payload = {
            "event_type": "CONVERSION",
            "event_family": "CDP",
            "payload": {
                "conversion_identifier": "veiculos_entregues",
                "name": nome,
                "email": email,
                "company_name": nome,
                "vehicle": modelo_carro,
                "cf_nome_da_empresa": empresa,
                "cf_consultor": consultor,
                "cf_modelo_do_carro": modelo_carro,
                "cf_ano_veiculo": ano_veiculo,
                "cf_tipo_veiculo": tipo_veiculo,
                "tags": ["veiculos_entregues", "NBS", modelo_carro],
                "traffic_source": "NBS",
                "traffic_campaign": "NBS"
            }
        }
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            if response.status_code in (200, 201):
                event_uuid = response.json().get("event_uuid")
                df_email.loc[_, 'COD_RDSTATION'] = event_uuid
            else:
                logger.error(
                    "RD Station rejeitou conversao HTTP %s para email %s: %s",
                    response.status_code,
                    email,
                    response.text,
                )
        except (requests.exceptions.RequestException, ValueError, TypeError) as e:
            logger.error("Erro ao enviar conversao para RD Station: %s", e)



planilha = BytesIO()
with pd.ExcelWriter(planilha, engine="xlsxwriter") as writer:
    df.to_excel(writer, index=False, sheet_name="VEICULOS_ENTREGUES")
    df_email.to_excel(writer, index=False, sheet_name="Emails")
    leads_sem_email.to_excel(writer, index=False, sheet_name="Sem Email")
    _format_sheet_as_table(writer, df, "VEICULOS_ENTREGUES")
    _format_sheet_as_table(writer, df_email, "Emails")
    _format_sheet_as_table(writer, leads_sem_email, "Sem Email")

planilha.seek(0)

# envia planilha para o telegram do pablo
url = f"https://api.telegram.org/bot{TOKEN}/sendDocument"
logger.info("Gerando relatorio Planilha...")
message = f"Relatorio Veiculos Entregues - {now.strftime('%d/%m/%Y')}"
files = {
    "document": ("relatorio_veiculos_entregues.xlsx", planilha.getvalue())
}
data = {
    "chat_id": TELEGRAM_CHATS["Pablo"],
    "caption": message
}
response = requests.post(url, data=data, files=files)
logger.info("Relatorio enviado para o Telegram: %s", response.status_code)



cur.close()
conn.close()
