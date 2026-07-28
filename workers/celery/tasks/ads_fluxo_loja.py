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
	WHEN c.nome = 'Consumidor Final' THEN ce.NOME_CLIENTE_AVULSO
	ELSE
		c.nome
    END nome,
    eu.NOME_COMPLETO responsavel,
    ce.EMAIL, ce.EMAIL_CLIENTE_AVULSO, c.EMAIL_NFE, c.EMAIL2, ce.COD_PROPOSTA, ce.COD_PROPOSTA_MONTADA, pm.DESCRICAO_MODELO,
    fone_cliente_avulso
FROM
    CRM_EVENTOS ce
LEFT JOIN EMPRESAS_USUARIOS eu ON
    eu.nome = ce.RESPONSAVEL_PELO_EVENTO
LEFT JOIN CRM_ANDAMENTO ca ON
    ca.COD_ANDAMENTO = ce.COD_ANDAMENTO
LEFT JOIN MIDIA m ON
    m.COD_MIDIA = ce.COD_MIDIA 
LEFT JOIN clientes c ON
    ce.COD_CLIENTE = c.COD_CLIENTE
LEFT JOIN CRM_EVENTOS_TIPO cet ON 
    cet.COD_TIPO_EVENTO = ce.COD_TIPO_EVENTO
LEFT JOIN CRM_DESCARTES cd ON 
    cd.COD_DESCARTE = ce.COD_DESCARTE
LEFT JOIN CRM_MOTIVO_PERDAS cmp ON 
    cmp.cod_motivo_perda = ce.cod_motivo_perda
LEFT JOIN produtos_modelos pm ON 
    pm.COD_PRODUTO = ce.COD_PRODUTO AND pm.COD_MODELO = ce.COD_MODELO
LEFT JOIN caiuas_crm_eventos_descartados ced ON 
    ced.cod_empresa = ce.COD_EMPRESA AND ced.cod_evento = ce.COD_EVENTO
WHERE
    ce.cod_tipo_evento IN (
        '785','807'
    )
    AND TRUNC(ce.DATA_CRIACAO) >= TO_DATE('{initial_date.strftime("%Y-%m-%d")}', 'YYYY-MM-DD')
    AND TRUNC(ce.DATA_CRIACAO) <= TO_DATE('{now.strftime("%Y-%m-%d")}', 'YYYY-MM-DD')
 """

 
conn, cur = oracle()
cur.execute(query)
result = cur.fetchall()
columns = [desc[0] for desc in cur.description]
df = pd.DataFrame(result, columns=columns)

query = f"""
    SELECT
	CASE 
	WHEN c.nome = 'Consumidor Final' THEN ce.NOME_CLIENTE_AVULSO
	ELSE
		c.nome
    END nome,
    eu.NOME_COMPLETO responsavel,
    ce.EMAIL, ce.EMAIL_CLIENTE_AVULSO, c.EMAIL_NFE, c.EMAIL2, ce.COD_PROPOSTA, ce.COD_PROPOSTA_MONTADA, pm.DESCRICAO_MODELO,
    fone_cliente_avulso
FROM
    CRM_EVENTOS ce
LEFT JOIN EMPRESAS_USUARIOS eu ON
    eu.nome = ce.RESPONSAVEL_PELO_EVENTO
LEFT JOIN CRM_ANDAMENTO ca ON
    ca.COD_ANDAMENTO = ce.COD_ANDAMENTO
LEFT JOIN MIDIA m ON
    m.COD_MIDIA = ce.COD_MIDIA 
LEFT JOIN clientes c ON
    ce.COD_CLIENTE = c.COD_CLIENTE
LEFT JOIN CRM_EVENTOS_TIPO cet ON 
    cet.COD_TIPO_EVENTO = ce.COD_TIPO_EVENTO
LEFT JOIN CRM_DESCARTES cd ON 
    cd.COD_DESCARTE = ce.COD_DESCARTE
LEFT JOIN CRM_MOTIVO_PERDAS cmp ON 
    cmp.cod_motivo_perda = ce.cod_motivo_perda
LEFT JOIN produtos_modelos pm ON 
    pm.COD_PRODUTO = ce.COD_PRODUTO AND pm.COD_MODELO = ce.COD_MODELO
LEFT JOIN caiuas_crm_eventos_descartados ced ON 
    ced.cod_empresa = ce.COD_EMPRESA AND ced.cod_evento = ce.COD_EVENTO
WHERE
    ce.cod_tipo_evento IN (
        '829','831','795','793','797','799','819','821','785','807','815','817','810','812'
    )
    AND TRUNC(ce.DATA_VISITA) >= TO_DATE('{initial_date.strftime("%Y-%m-%d")}', 'YYYY-MM-DD')
    AND TRUNC(ce.DATA_VISITA) <= TO_DATE('{now.strftime("%Y-%m-%d")}', 'YYYY-MM-DD')
"""
cur.execute(query)
result = cur.fetchall()
columns = [desc[0] for desc in cur.description]
df_visita = pd.DataFrame(result, columns=columns)
df = pd.concat([df, df_visita]).drop_duplicates().reset_index(drop=True)

email = df[['NOME','EMAIL_NFE','COD_PROPOSTA','DESCRICAO_MODELO','FONE_CLIENTE_AVULSO']]
# renomeia colunas
email = email.rename(columns={'NOME': 'Nome', 'EMAIL_NFE': 'Email'})
email2 = df[['NOME','EMAIL2','COD_PROPOSTA','DESCRICAO_MODELO','FONE_CLIENTE_AVULSO']]
email2 = email2.rename(columns={'NOME': 'Nome', 'EMAIL2': 'Email'})
email_cliente_avulso = df[['NOME','EMAIL_CLIENTE_AVULSO','COD_PROPOSTA','DESCRICAO_MODELO','FONE_CLIENTE_AVULSO']]
email_cliente_avulso = email_cliente_avulso.rename(columns={'NOME': 'Nome', 'EMAIL_CLIENTE_AVULSO': 'Email'})

df_email = pd.concat([email, email2, email_cliente_avulso]).drop_duplicates().reset_index(drop=True)
df_email = df_email[df_email['Email'].notna() & (df_email['Email'] != '')]
# reduz rejeicoes 400 por email malformado
df_email = df_email[df_email['Email'].str.contains(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", na=False)]

# gera um df com todos os contatos que não tem email nenhum
mask_sem_email = df[['EMAIL_NFE', 'EMAIL2', 'EMAIL_CLIENTE_AVULSO']].isna().all(axis=1)
leads_sem_email = df[mask_sem_email].reset_index(drop=True)

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
        telefone = _safe_str(linha.get('FONE_CLIENTE_AVULSO'))
        veiculo = _safe_str(linha.get('DESCRICAO_MODELO'))
        cod_proposta = _safe_str(linha.get('COD_PROPOSTA'))
        if not cod_proposta:
            payload = {
                "event_type": "CONVERSION",
                "event_family": "CDP",
                "payload": {
                    "conversion_identifier": "fluxo_loja_sem_proposta",
                    "name": nome,
                    "email": email,
                    "mobile_phone": telefone,
                    "company_name": nome,
                    "vehicle": veiculo,
                    "tags": ["fluxo_loja_sem_proposta", "NBS", veiculo],
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
    df.to_excel(writer, index=False, sheet_name="CRM_EVENTOS")
    df_email.to_excel(writer, index=False, sheet_name="Emails")
    leads_sem_email.to_excel(writer, index=False, sheet_name="Leads sem Email")
    _format_sheet_as_table(writer, df, "CRM_EVENTOS")
    _format_sheet_as_table(writer, df_email, "Emails")
    _format_sheet_as_table(writer, leads_sem_email, "Leads sem Email")

planilha.seek(0)

# envia planilha para o telegram do pablo
url = f"https://api.telegram.org/bot{TOKEN}/sendDocument"
logger.info("Gerando relatorio Planilha...")
message = f"Relatorio Fluxo Loja - {now.strftime('%d/%m/%Y')}"
files = {
    "document": ("relatorio.xlsx", planilha.getvalue())
}
data = {
    "chat_id": TELEGRAM_CHATS["Pablo"],
    "caption": message
}
response = requests.post(url, data=data, files=files)
logger.info("Relatorio enviado para o Telegram: %s", response.status_code)



cur.close()
conn.close()