import base64
import datetime
import html
import os
import sys
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from io import BytesIO
from pathlib import Path

import pandas as pd
import requests
from requests_aws4auth import AWS4Auth

try:
    from database import oracle
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from database import oracle

SES_REGION = "sa-east-1"
SES_SENDER = "pablo@caiuas.com.br"
SES_RECIPIENTS = [
    "opabloedu@gmail.com",
    "marcelotcf@caiuas.com.br",
    "ricardo.camargo@caiuas.com.br",
]
RELATORIO_NOME = "Veículos no chão sem faturamento"

COLUNAS_AMIGAVEIS = {
    "data_proposta": "Data Proposta",
    "data_veiculo_chegou": "Chegada do Veículo",
    "nome_vendedor": "Vendedor",
    "modelo": "Modelo",
    "cor": "Cor",
    "chassi_completo": "Chassi",
    "nome_cliente": "Cliente",
    "novo_usado": "Novo/Usado",
}

query = """
    SELECT 
        vp.EMISSAO data_proposta,
        crv.created_at data_veiculo_chegou,
        eu.NOME_COMPLETO nome_vendedor, 
        pm.DESCRICAO_MODELO modelo, 
        COALESCE(ce.DESCRICAO, ce2.DESCRICAO) cor, 
        v.CHASSI_COMPLETO, 
        c.NOME nome_cliente,
        CASE 
            WHEN v.novo_usado = 'U' THEN 'Usado'
            WHEN v.COD_PROPOSTA_INTERNET IS NOT NULL OR vp.INTERNET = 'F' THEN 'Direta'
            ELSE
                'Novo'
        END novo_usado
    FROM VEICULOS_PROPOSTAS vp
    LEFT JOIN veiculos v ON 1=1
        AND v.CHASSI_RESUMIDO = vp.CHASSI_RESUMIDO 
        AND v.STATUS = 'E'
    LEFT JOIN produtos pr ON 1=1
        AND pr.COD_PRODUTO = vp.COD_PRODUTO 
    LEFT JOIN prop_ficticia_dados pfd ON 1=1
        AND pfd.COD_FICTICIO = vp.COD_FICTICIO
    LEFT JOIN CORES_EXTERNAS ce ON 1=1
        AND ce.COR_EXTERNA = v.COR_EXTERNA 
    LEFT JOIN CORES_EXTERNAS ce2 ON 1=1
        AND ce2.COR_EXTERNA = pfd.COR_EXTERNA
    LEFT JOIN produtos_modelos pm ON 1=1
        AND pm.COD_PRODUTO = vp.COD_PRODUTO 
        AND pm.COD_MODELO = vp.COD_MODELO 
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
    LEFT JOIN (
        SELECT
            ea.COD_PROPOSTA,
            MAX(ea.DATA_AGENDADA) DATA_AGENDADA,
            MAX(ea.DATA_BAIXA) DATA_BAIXA,
            MAX(es.DESCRICAO_SALA) local_entrega
        FROM EV_AGENDADOS ea
        LEFT JOIN EV_SALAS es ON 1=1
            AND es.cod_sala = ea.COD_SALA
        WHERE ea.STATUS <> 'C'
        GROUP BY ea.COD_PROPOSTA
    ) ea ON 1=1
        AND ea.COD_PROPOSTA = vp.COD_PROPOSTA
    left join caiuas_veic_proc cvp on 1=1
        and cvp.cod_proposta = vp.cod_proposta
    LEFT JOIN caiuas_recebimento_veiculo crv ON 1=1
        AND crv.cod_modelo = v.COD_MODELO 
        AND crv.cod_produto = v.COD_PRODUTO 
        AND crv.chassi_resumido = v.CHASSI_RESUMIDO 
        AND crv.cod_empresa = v.COD_EMPRESA
    LEFT JOIN veiculos_pedidos vp2 ON 1=1
        AND vp2.cod_pedido = vp.cod_pedido
    WHERE vp.STATUS_PROPOSTA NOT IN ('C','V')
        AND vp.VENDEDOR <> 'DIRETORIA'
        AND TRUNC(vp.EMISSAO ) >= TO_DATE('2025-09-01', 'YYYY-MM-DD')
        AND crv.created_at IS NOT null
    ORDER BY crv.created_at
"""


def send_email(subject, body, destinatarios, anexos=None):
    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = SES_SENDER
    msg["To"] = ", ".join(destinatarios)
    msg.attach(MIMEText(body, "html", "utf-8"))

    for nome_arquivo, dados in (anexos or []):
        parte = MIMEApplication(dados, _subtype="xlsx")
        parte.add_header("Content-Disposition", "attachment", filename=nome_arquivo)
        msg.attach(parte)

    raw = base64.b64encode(msg.as_bytes()).decode()

    auth = AWS4Auth(
        os.environ["AWS_ACCESS_KEY_ID"],
        os.environ["AWS_SECRET_ACCESS_KEY"],
        SES_REGION,
        "ses",
        session_token=os.environ.get("AWS_SESSION_TOKEN"),
    )
    payload = {
        "FromEmailAddress": SES_SENDER,
        "Destination": {"ToAddresses": destinatarios},
        "Content": {"Raw": {"Data": raw}},
    }
    return requests.post(
        f"https://email.{SES_REGION}.amazonaws.com/v2/email/outbound-emails",
        auth=auth,
        json=payload,
        timeout=30,
    )


def formatar_valor(valor):
    if valor is None:
        return ""
    try:
        if pd.isna(valor):
            return ""
    except (TypeError, ValueError):
        pass
    if isinstance(valor, (datetime.datetime, datetime.date, pd.Timestamp)):
        if isinstance(valor, pd.Timestamp):
            valor = valor.to_pydatetime()
        if isinstance(valor, datetime.datetime):
            return valor.strftime("%d/%m/%Y %H:%M")
        return valor.strftime("%d/%m/%Y")
    return str(valor)


def formatar_sheet_como_tabela(writer, dataframe, sheet_name):
    worksheet = writer.sheets[sheet_name]
    n_rows, n_cols = dataframe.shape

    if n_cols == 0:
        return

    header_format = writer.book.add_format({"bold": True})
    worksheet.set_row(0, None, header_format)

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


def renomear_colunas(dataframe):
    return dataframe.rename(
        columns={
            col: COLUNAS_AMIGAVEIS.get(col.lower(), col)
            for col in dataframe.columns
        }
    )


def montar_planilha(dataframe):
    planilha = BytesIO()
    with pd.ExcelWriter(planilha, engine="xlsxwriter") as writer:
        dataframe.to_excel(writer, index=False, sheet_name="Veículos")
        formatar_sheet_como_tabela(writer, dataframe, "Veículos")
    planilha.seek(0)
    return planilha.getvalue()


def montar_corpo_tabela(dataframe):
    cabecalho = "".join(
        f'<th style="border:1px solid #ddd;padding:6px 10px;background:#cc0000;'
        f'color:#fff;text-align:left">{html.escape(str(col))}</th>'
        for col in dataframe.columns
    )
    linhas = "".join(
        "<tr>"
        + "".join(
            f'<td style="border:1px solid #ddd;padding:6px 10px">'
            f'{html.escape(formatar_valor(valor))}</td>'
            for valor in linha
        )
        + "</tr>"
        for linha in dataframe.itertuples(index=False)
    )
    return f"""
    <table style="border-collapse:collapse;font-family:Arial,Helvetica,sans-serif;font-size:13px">
      <thead><tr>{cabecalho}</tr></thead>
      <tbody>{linhas}</tbody>
    </table>
    """


def main():
    conn, cur = oracle()
    try:
        cur.execute(query)
        resultado = cur.fetchall()
        colunas = [desc[0] for desc in cur.description]
    finally:
        cur.close()
        conn.close()

    total = len(resultado)
    hoje = datetime.datetime.now().strftime("%d/%m/%Y")

    if total == 0:
        corpo = f"""
        <div style="font-family:Arial,Helvetica,sans-serif;font-size:15px;color:#222">
          <h2 style="color:#cc0000;margin:0 0 12px">{html.escape(RELATORIO_NOME)}</h2>
          <p>Não há veículos no chão sem faturamento em {hoje}.</p>
        </div>
        """
        resposta = send_email(
            f"{RELATORIO_NOME} - {hoje}",
            corpo,
            SES_RECIPIENTS,
        )
        print("Sem resultados.", resposta.status_code, resposta.text)
        return

    df = pd.DataFrame(resultado, columns=colunas)

    for coluna in df.columns:
        if "data" in coluna.lower() or "chegou" in coluna.lower():
            df[coluna] = pd.to_datetime(df[coluna], errors="coerce")

    df = renomear_colunas(df)

    planilha = montar_planilha(df)

    corpo = f"""
    <div style="font-family:Arial,Helvetica,sans-serif;font-size:15px;color:#222;max-width:900px">
      <h2 style="color:#cc0000;margin:0 0 4px">{html.escape(RELATORIO_NOME)}</h2>
      <p style="margin:0 0 16px">Total de veículos no chão sem faturamento: <b>{total}</b> - {hoje}</p>
      {montar_corpo_tabela(df)}
      <p style="margin:16px 0 0;color:#666">Planilha completa em anexo.</p>
    </div>
    """

    resposta = send_email(
        f"{RELATORIO_NOME} - {hoje}",
        corpo,
        SES_RECIPIENTS,
        anexos=[("veiculos_no_chao_sem_faturamento.xlsx", planilha)],
    )
    print(total, resposta.status_code, resposta.text)


if __name__ == "__main__":
    main()
