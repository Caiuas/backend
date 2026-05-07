import os
import logging
import datetime
import requests
from io import BytesIO
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import numpy as np
from app import app
from database import oracle

logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT", "")
TELEGRAM_CHATS = {
    "Pablo": "548519349",
    "Cristiane": "8703967479",
}

COR_VERMELHO = "#D50000"
COR_AZUL = "#337AB7"
COR_CINZA = "#D8DCE3"
COR_FUNDO = "#FFFFFF"
COR_TEXTO = "#2C3E50"


def _conexao():
    conn, cursor = oracle()
    return conn, cursor


def _fetch_agendamentos(data_agenda):
    query = f"""
        SELECT
            c.NOME,
            t_tel.TELEFONES AS TELEFONE,
            eu.NOME_COMPLETO AS QUEM_AGENDOU,
            oa.PLACA,
            pm.DESCRICAO_MODELO,
            TO_CHAR(s.data_comeca, 'HH24:MI') AS HORARIO_AGENDAMENTO,
            CASE
                WHEN EXISTS (
                    SELECT 1
                    FROM caiuas_os_agenda_tags oat
                    INNER JOIN caiuas_tags ct ON oat.id_tag = ct.id_tag
                    WHERE oat.cod_empresa = oa.COD_EMPRESA
                      AND oat.cod_os_agenda = oa.COD_OS_AGENDA
                      AND UPPER(ct.name) = 'EXPRESS'
                ) THEN 'S'
                ELSE 'N'
            END AS EXPRESS,
            rec.RECLAMACOES
        FROM os_agenda_servicos s
        LEFT JOIN CRM_EVENTOS ce
            ON ce.COD_EMPRESA = s.crm_cod_empresa
            AND ce.COD_EVENTO = s.CRM_COD_EVENTO
        LEFT JOIN OS_AGENDA oa
            ON oa.COD_EMPRESA = s.COD_EMPRESA
            AND oa.COD_OS_AGENDA = s.COD_OS_AGENDA
        LEFT JOIN CLIENTES c
            ON c.COD_CLIENTE = oa.cod_cliente
        LEFT JOIN PRISMA_BOX pb
            ON pb.PRISMA = oa.PRISMA
        LEFT JOIN produtos p
            ON p.COD_PRODUTO = oa.COD_PRODUTO
        LEFT JOIN PRODUTOS_MODELOS pm
            ON pm.COD_PRODUTO = oa.COD_PRODUTO
            AND pm.COD_MODELO = oa.COD_MODELO
        LEFT JOIN EMPRESAS_USUARIOS eu
            ON eu.nome = ce.RESPONSAVEL_PELO_EVENTO
        LEFT JOIN os o
            ON oa.COD_EMPRESA = o.COD_EMPRESA
            AND oa.COD_OS_AGENDA = o.COD_OS_AGENDA
            AND o.ORCAMENTO <> 'S'
        LEFT JOIN empresas_usuarios eu2
            ON eu2.NOME = oa.CONSULTOR
        LEFT JOIN empresas_usuarios eu3
            ON eu3.NOME = oa.quem_abriu
        LEFT JOIN (
            SELECT
                cod_cliente,
                LISTAGG(tel, ' | ') WITHIN GROUP (ORDER BY tel) AS TELEFONES
            FROM (
                SELECT DISTINCT cod_cliente, tel
                FROM (
                    SELECT COD_CLIENTE, TRIM(PREFIXO_CEL) || TRIM(TELEFONE_CEL) AS tel FROM clientes WHERE TELEFONE_CEL IS NOT NULL
                    UNION ALL
                    SELECT COD_CLIENTE, TRIM(PREFIXO_RES) || TRIM(TELEFONE_RES) FROM clientes WHERE TELEFONE_RES IS NOT NULL
                    UNION ALL
                    SELECT COD_CLIENTE, TRIM(PREFIXO_COM) || TRIM(TELEFONE_COM) FROM clientes WHERE TELEFONE_COM IS NOT NULL
                    UNION ALL
                    SELECT COD_CLIENTE, TRIM(PREFIXO_MSG_TXT_INST) || TRIM(NUMERO_MSG_TXT_INST) FROM clientes WHERE NUMERO_MSG_TXT_INST IS NOT NULL
                )
            )
            GROUP BY cod_cliente
        ) t_tel
            ON t_tel.cod_cliente = c.COD_CLIENTE
        LEFT JOIN (
            SELECT
                cod_empresa,
                cod_os_agenda,
                LISTAGG(descricao, ' | ') WITHIN GROUP (ORDER BY descricao) AS RECLAMACOES
            FROM OS_AGENDA_RECLAMACAO
            GROUP BY cod_empresa, cod_os_agenda
        ) rec
            ON rec.cod_empresa = oa.COD_EMPRESA
            AND rec.cod_os_agenda = oa.COD_OS_AGENDA
        WHERE
            pb.COD_EMPRESA_FILTRO = 11
            AND oa.PRISMA IS NOT NULL
            AND TRUNC(s.data_comeca) = TRUNC(TO_DATE('{data_agenda}', 'YYYY-MM-DD'))
        ORDER BY
            s.data_comeca
    """
    conn, cursor = _conexao()
    try:
        cursor.execute(query)
        result = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        df = pd.DataFrame(result, columns=columns)
        return df
    finally:
        cursor.close()
        conn.close()


def _gerar_excel(df, data_agenda):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Agendamentos", startrow=1)
        workbook = writer.book
        worksheet = writer.sheets["Agendamentos"]

        worksheet.set_row(0, 45)
        title_format = workbook.add_format({
            "bold": True,
            "font_size": 16,
            "align": "center",
            "valign": "vcenter",
            "font_name": "Calibri",
            "font_color": COR_VERMELHO,
        })
        max_col = len(df.columns) - 1
        data_formatada = datetime.datetime.strptime(data_agenda, "%Y-%m-%d").strftime("%d/%m/%Y")
        worksheet.merge_range(0, 0, 0, max_col, f"Agendamentos - {data_formatada}", title_format)

        header_format = workbook.add_format({
            "bold": True,
            "font_color": "white",
            "bg_color": COR_AZUL,
            "border": 1,
            "align": "center",
            "valign": "vcenter",
            "font_name": "Calibri",
            "font_size": 10,
        })
        cell_format = workbook.add_format({
            "border": 1,
            "align": "left",
            "valign": "vcenter",
            "font_name": "Calibri",
            "font_size": 9,
            "text_wrap": True,
        })

        col_widths = {
            "NOME": 30, "TELEFONE": 22, "QUEM_AGENDOU": 20,
            "PLACA": 12, "DESCRICAO_MODELO": 20, "HORARIO_AGENDAMENTO": 14,
            "EXPRESS": 8, "RECLAMACOES": 35,
        }
        for i, col in enumerate(df.columns):
            width = col_widths.get(col, 15)
            worksheet.set_column(i, i, width)
            worksheet.write(1, i, col, header_format)
            for row_idx, val in enumerate(df[col], start=2):
                worksheet.write(row_idx, i, val, cell_format)

        worksheet.autofilter(1, 0, len(df) + 1, max_col)
        worksheet.freeze_panes(2, 0)

    output.seek(0)
    return output.read()


def _gerar_pdf(df, data_agenda):
    data_formatada = datetime.datetime.strptime(data_agenda, "%Y-%m-%d").strftime("%d/%m/%Y")
    n_rows = len(df)
    row_height = 0.35
    fig_height = max(6, 1.2 + n_rows * row_height + 1.0)
    fig = plt.figure(figsize=(12, fig_height), facecolor=COR_FUNDO)

    fig.text(0.5, 0.97, f"Agendamentos - {data_formatada}", fontsize=16, ha="center",
             weight="bold", color=COR_VERMELHO, family="sans-serif")
    fig.text(0.5, 0.94, f"Total: {n_rows} agendamento(s)", fontsize=9, ha="center",
             color="#7F8C8D", family="sans-serif")

    if n_rows > 0:
        col_labels = list(df.columns)
        cell_text = df.values.tolist()
        col_widths = [0.18, 0.14, 0.12, 0.08, 0.14, 0.10, 0.05, 0.19]

        ax_tb = fig.add_axes([0.03, 0.02, 0.94, 0.90])
        ax_tb.axis("off")

        t = ax_tb.table(
            cellText=cell_text,
            colLabels=col_labels,
            colWidths=col_widths,
            loc="upper center",
            cellLoc="left",
        )
        t.auto_set_font_size(False)
        t.set_fontsize(7)
        t.scale(1, 1.3)

        for key, cell in t.get_celld().items():
            cell.set_edgecolor(COR_CINZA)
            cell.set_linewidth(0.3)
            if key[0] == 0:
                cell.set_text_props(weight="bold", color="white", family="sans-serif", fontsize=8)
                cell.set_facecolor(COR_AZUL)
            else:
                cell.set_facecolor(COR_FUNDO)
                cell.set_text_props(color=COR_TEXTO, family="sans-serif", fontsize=7)
                if key[1] == 0:
                    cell.set_text_props(weight="bold", family="sans-serif", fontsize=7, color=COR_TEXTO)

    buf = BytesIO()
    plt.savefig(buf, format="pdf", bbox_inches="tight", dpi=150)
    plt.close()
    buf.seek(0)
    return buf.read()


def _enviar_telegram(nome, chat_id, pdf_data, excel_data, data_agenda, titulo):
    url = f"https://api.telegram.org/bot{TOKEN}/sendDocument"
    data_formatada = datetime.datetime.strptime(data_agenda, "%Y-%m-%d").strftime("%d/%m/%Y")
    resultados = []

    arquivos = [
        ("agendamentos.pdf", pdf_data, f"Agendamentos {data_formatada} (PDF)"),
        ("agendamentos.xlsx", excel_data, f"Agendamentos {data_formatada} (Excel)"),
    ]

    for filename, filedata, caption in arquivos:
        dados = {"chat_id": chat_id, "caption": caption}
        try:
            arquivo = {"document": (f"{titulo}_{data_agenda}_{filename}", filedata)}
            resposta = requests.post(url, data=dados, files=arquivo, timeout=30)
            if resposta.status_code == 200:
                logger.info("Enviado %s para %s.", filename, nome)
                resultados.append(True)
            else:
                logger.error("Falha %s para %s: %s", filename, nome, resposta.json())
                resultados.append(False)
        except Exception as exc:
            logger.error("Erro %s para %s: %s", filename, nome, exc)
            resultados.append(False)

    return all(resultados)


@app.task(bind=True, max_retries=2, default_retry_delay=120)
def prospeccao_oficina_hoje(self):
    hoje = datetime.date.today()
    data_agenda = hoje.strftime("%Y-%m-%d")
    logger.info("prospeccao_oficina: gerando relatorio para HOJE (%s)", data_agenda)

    try:
        df = _fetch_agendamentos(data_agenda)
        df = df.fillna("")

        if df.empty:
            logger.info("prospeccao_oficina: nenhum agendamento para hoje")
            return {"status": "no_data", "data": data_agenda}

        pdf_data = _gerar_pdf(df, data_agenda)
        excel_data = _gerar_excel(df, data_agenda)

        for nome, chat_id in TELEGRAM_CHATS.items():
            _enviar_telegram(nome, chat_id, pdf_data, excel_data, data_agenda, "hoje")

        logger.info("prospeccao_oficina: relatorio hoje enviado com %d agendamentos", len(df))
        return {"status": "success", "data": data_agenda, "total": len(df)}

    except Exception as exc:
        logger.error("prospeccao_oficina: erro hoje: %s", exc)
        raise self.retry(exc=exc)


@app.task(bind=True, max_retries=2, default_retry_delay=120)
def prospeccao_oficina_amanha(self):
    amanha = datetime.date.today() + datetime.timedelta(days=1)
    data_agenda = amanha.strftime("%Y-%m-%d")
    logger.info("prospeccao_oficina: gerando relatorio para AMANHA (%s)", data_agenda)

    try:
        df = _fetch_agendamentos(data_agenda)
        df = df.fillna("")

        if df.empty:
            logger.info("prospeccao_oficina: nenhum agendamento para amanha")
            return {"status": "no_data", "data": data_agenda}

        pdf_data = _gerar_pdf(df, data_agenda)
        excel_data = _gerar_excel(df, data_agenda)

        for nome, chat_id in TELEGRAM_CHATS.items():
            _enviar_telegram(nome, chat_id, pdf_data, excel_data, data_agenda, "amanha")

        logger.info("prospeccao_oficina: relatorio amanha enviado com %d agendamentos", len(df))
        return {"status": "success", "data": data_agenda, "total": len(df)}

    except Exception as exc:
        logger.error("prospeccao_oficina: erro amanha: %s", exc)
        raise self.retry(exc=exc)
