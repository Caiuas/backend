import os
import logging
import datetime
import requests
from io import BytesIO
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from matplotlib.backends.backend_pdf import PdfPages
from app import app
from database import oracle

logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT", "")
TELEGRAM_CHATS = {
    "Pablo": "548519349",
    "Cristiane": "8703967479",
    "Fabio": "8653376419",
}

COR_VERMELHO = "#D50000"
COR_AZUL = "#337AB7"
COR_CINZA = "#D8DCE3"
COR_FUNDO = "#FFFFFF"
COR_TEXTO = "#2C3E50"
COR_CANCELADO = "#E74C3C"


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
    n_total = len(df)
    hoje_str = datetime.datetime.strptime(data_agenda, "%Y-%m-%d").strftime("%d/%m/%Y")
    dia_semana = datetime.datetime.strptime(data_agenda, "%Y-%m-%d").strftime("%A")
    dias_pt = {"Monday": "Segunda", "Tuesday": "Terca", "Wednesday": "Quarta", "Thursday": "Quinta",
               "Friday": "Sexta", "Saturday": "Sabado", "Sunday": "Domingo"}
    dia_semana_pt = dias_pt.get(dia_semana, dia_semana)

    df = df.fillna("")

    fig_w = 8.27
    fig_h = 11.69

    cols = 3
    margin_left = 0.30
    margin_right = 0.30
    margin_top = 1.00
    margin_bottom = 0.35
    gap_x = 0.12
    gap_y = 0.10

    card_w = (fig_w - margin_left - margin_right - gap_x * (cols - 1)) / cols
    card_h = 1.15
    usable_h = fig_h - margin_top - margin_bottom
    rows_per_page = max(1, int((usable_h + gap_y) / (card_h + gap_y)))
    cards_per_page = rows_per_page * cols

    buf = BytesIO()

    with PdfPages(buf) as pdf:
        pages = max(1, (n_total + cards_per_page - 1) // cards_per_page)

        for page in range(pages):
            fig = plt.figure(figsize=(fig_w, fig_h), facecolor=COR_FUNDO)

            fig.text(0.5, 0.975, f"Agendamentos - {hoje_str} ({dia_semana_pt})", fontsize=13,
                     ha="center", weight="bold", color=COR_VERMELHO, family="sans-serif")
            fig.text(0.5, 0.952, f"Total: {n_total} agendamento(s)", fontsize=7, ha="center",
                     color="#7F8C8D", family="sans-serif")

            start_idx = page * cards_per_page
            end_idx = min(start_idx + cards_per_page, n_total)

            for idx in range(start_idx, end_idx):
                local = idx - start_idx
                col = local % cols
                row = local // cols

                x_inch = margin_left + col * (card_w + gap_x)
                y_inch = fig_h - margin_top - (row + 1) * card_h - row * gap_y

                row_data = df.iloc[idx]

                ax = fig.add_axes([
                    x_inch / fig_w,
                    y_inch / fig_h,
                    card_w / fig_w,
                    card_h / fig_h,
                ])
                ax.axis("off")

                box = FancyBboxPatch(
                    (0, 0), 1, 1, boxstyle="round,pad=0.04",
                    facecolor=COR_FUNDO, edgecolor=COR_CINZA, linewidth=0.8,
                    transform=ax.transAxes, zorder=0,
                )
                ax.add_patch(box)

                nome = str(row_data.get("NOME", "")).strip()
                horario = str(row_data.get("HORARIO_AGENDAMENTO", "")).strip()
                placa = str(row_data.get("PLACA", "")).strip()
                modelo = str(row_data.get("DESCRICAO_MODELO", "")).strip()
                telefone = str(row_data.get("TELEFONE", "")).strip()
                quem_agendou = str(row_data.get("QUEM_AGENDOU", "")).strip()
                express = str(row_data.get("EXPRESS", "")).strip().upper()
                reclamacoes = str(row_data.get("RECLAMACOES", "")).strip()

                y_pos = 0.90
                ax.text(0.08, y_pos, nome[:35], fontsize=8, weight="bold",
                        color=COR_TEXTO, family="sans-serif", verticalalignment="top")

                y_pos -= 0.18
                if horario:
                    ax.text(0.08, y_pos, horario, fontsize=9, weight="bold",
                            color=COR_AZUL, family="sans-serif", verticalalignment="top")
                if placa:
                    ax.text(0.45, y_pos, f"|  {placa.upper()}", fontsize=7,
                            color=COR_TEXTO, family="sans-serif", verticalalignment="top")

                y_pos -= 0.16
                if modelo:
                    ax.text(0.08, y_pos, modelo[:30], fontsize=7,
                            color=COR_TEXTO, family="sans-serif", verticalalignment="top")

                y_pos -= 0.15
                if telefone:
                    ax.text(0.08, y_pos, telefone[:38], fontsize=5.5,
                            color="#7F8C8D", family="sans-serif", verticalalignment="top")

                y_pos -= 0.13
                if quem_agendou:
                    ax.text(0.08, y_pos, f"Agendado por: {quem_agendou[:25]}", fontsize=5,
                            color="#95A5A6", family="sans-serif", verticalalignment="top")

                if express == "S":
                    badge = FancyBboxPatch(
                        (0.72, 0.84), 0.25, 0.12, boxstyle="round,pad=0.02",
                        facecolor=COR_VERMELHO, edgecolor="none",
                        transform=ax.transAxes, zorder=2,
                    )
                    ax.add_patch(badge)
                    ax.text(0.845, 0.90, "EXPRESS", fontsize=5, weight="bold",
                            color="white", ha="center", va="center",
                            family="sans-serif", transform=ax.transAxes)

                if reclamacoes:
                    ax.text(0.08, 0.05, f"Rec: {reclamacoes[:45]}", fontsize=4.5,
                            color=COR_CANCELADO, family="sans-serif",
                            verticalalignment="bottom", style="italic")

            pdf.savefig(fig)
            plt.close(fig)

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
