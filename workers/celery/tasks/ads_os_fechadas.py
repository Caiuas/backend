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
	e.NOME cf_nome_da_empresa,
	c.nome nome_cliente,
    eu.NOME_COMPLETO cf_consultor,
    c.EMAIL_NFE email,
    concat(concat(pm.DESCRICAO_MODELO, ' - '),odv.ANO) cf_modelo_do_carro,
    odv.ANO cf_ano_veiculo
FROM os os
LEFT JOIN OS_DADOS_VEICULOS odv ON 1=1
	AND os.COD_EMPRESA = odv.COD_EMPRESA
	AND os.NUMERO_OS = odv.NUMERO_OS
LEFT JOIN clientes c ON 1=1
	AND c.COD_CLIENTE = os.COD_CLIENTE
LEFT JOIN EMPRESAS_USUARIOS eu on 1=1
	AND eu.nome = os.nome
LEFT JOIN produtos_modelos pm ON 1=1
	AND pm.COD_PRODUTO = odv.COD_PRODUTO
	AND pm.COD_MODELO = odv.COD_MODELO
LEFT JOIN empresas e ON 1=1
	AND e.COD_EMPRESA = os.COD_EMPRESA
WHERE 1=1
	AND TRUNC(os.DATA_ENCERRADA) >= TO_DATE('{initial_date.strftime("%Y-%m-%d")}', 'YYYY-MM-DD')
	AND TRUNC(os.DATA_ENCERRADA) <= TO_DATE('{now.strftime("%Y-%m-%d")}', 'YYYY-MM-DD')
	AND os.STATUS_OS = 1
GROUP BY
	e.NOME,
	c.nome,
    eu.NOME_COMPLETO,
    c.EMAIL_NFE,
    pm.DESCRICAO_MODELO,
    odv.ANO
 """


conn, cur = oracle()
cur.execute(query)
result = cur.fetchall()
columns = [desc[0] for desc in cur.description]
df = pd.DataFrame(result, columns=columns)

df_email = df.copy()
# padroniza Nome/Email a partir das colunas da consulta de OS
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
        payload = {
            "event_type": "CONVERSION",
            "event_family": "CDP",
            "payload": {
                "conversion_identifier": "os_fechadas",
                "name": nome,
                "email": email,
                "company_name": nome,
                "vehicle": modelo_carro,
                "cf_nome_da_empresa": empresa,
                "cf_consultor": consultor,
                "cf_modelo_do_carro": modelo_carro,
                "cf_ano_veiculo": ano_veiculo,
                "tags": ["os_fechadas", "NBS", modelo_carro],
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
    df.to_excel(writer, index=False, sheet_name="OS_FECHADAS")
    df_email.to_excel(writer, index=False, sheet_name="Emails")
    leads_sem_email.to_excel(writer, index=False, sheet_name="Sem Email")
    _format_sheet_as_table(writer, df, "OS_FECHADAS")
    _format_sheet_as_table(writer, df_email, "Emails")
    _format_sheet_as_table(writer, leads_sem_email, "Sem Email")

planilha.seek(0)

# envia planilha para o telegram do pablo
url = f"https://api.telegram.org/bot{TOKEN}/sendDocument"
logger.info("Gerando relatorio Planilha...")
message = f"Relatorio OS Fechadas - {now.strftime('%d/%m/%Y')}"
files = {
    "document": ("relatorio_os_fechadas.xlsx", planilha.getvalue())
}
data = {
    "chat_id": TELEGRAM_CHATS["Pablo"],
    "caption": message
}
response = requests.post(url, data=data, files=files)
logger.info("Relatorio enviado para o Telegram: %s", response.status_code)



cur.close()
conn.close()
