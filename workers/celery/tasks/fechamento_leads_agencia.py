import io
import logging
import os
from datetime import datetime, timedelta

import pandas as pd
import psycopg2
import requests

from app import app
from database import oracle

logger = logging.getLogger(__name__)

WRP_PAGE_SIZE = 5000
CONV_PAGE_SIZE = 500
ORACLE_PAGE_SIZE = 500
LOGO_CANDIDATES = ("images/logo.png", "images/logo_honda.png", "/app/images/logo.png")


def _get_telegram_token():
    return os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_BOT", "")


def _send_telegram_message(chat_id, text):
    token = _get_telegram_token()
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN/TELEGRAM_BOT não configurado")
        return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=15,
        )
        resp.raise_for_status()
        return True
    except Exception as exc:
        logger.error("Erro ao enviar mensagem ao Telegram: %s", exc)
        return False


def _send_telegram_document(chat_id, filename, content_bytes, caption=None):
    token = _get_telegram_token()
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN/TELEGRAM_BOT não configurado")
        return False
    data = {"chat_id": chat_id}
    if caption:
        data["caption"] = caption
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendDocument",
            data=data,
            files={
                "document": (
                    filename,
                    content_bytes,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
            timeout=120,
        )
        resp.raise_for_status()
        return True
    except Exception as exc:
        logger.error("Erro ao enviar Excel ao Telegram: %s", exc)
        return False


def _chatwoot_psycopg2():
    return psycopg2.connect(
        dbname=os.getenv("CHATWOOT_DATABASE"),
        user=os.getenv("CHATWOOT_USERNAME"),
        password=os.getenv("CHATWOOT_PASSWORD"),
        host=os.getenv("CHATWOOT_HOST"),
        port=os.getenv("CHATWOOT_PORT"),
    )


def extrair_ddd(phone_number):
    digits = "".join(ch for ch in str(phone_number or "") if ch.isdigit())
    if not digits:
        return ""
    if digits.startswith("55") and len(digits) >= 12:
        digits = digits[2:]
    return digits[:2] if len(digits) >= 10 else ""


def _find_wrp_id_bound(cur, lo_all, hi_all, target_dt, is_min=True):
    lo, hi = lo_all, hi_all
    ans = lo_all if is_min else hi_all
    while lo <= hi:
        mid = (lo + hi) // 2
        cur.execute(
            "SELECT id, created_at FROM whatsapp_raw_payloads WHERE id >= %s ORDER BY id ASC LIMIT 1",
            (mid,),
        )
        row = cur.fetchone()
        if not row:
            hi = mid - 1
            continue
        rid, rdt = row
        if rdt <= target_dt:
            if is_min:
                ans = rid
            lo = rid + 1
        else:
            if not is_min:
                ans = rid
            hi = mid - 1
    if is_min:
        return max(lo_all, ans - 2000)
    return min(hi_all, ans + 2000)


def _fetch_chatwoot_paginated(data_inicial, data_final):
    columns = [
        "conversation_id",
        "account_id",
        "created_at",
        "link_campanha",
        "id_campanha",
        "link_crm",
        "responsavel",
        "team",
        "phone_number",
        "custom_attributes",
        "source_id",
        "nome_campanha",
        "nome_anuncio",
        "status",
    ]
    by_conv = {}

    conn = _chatwoot_psycopg2()
    cur = conn.cursor()
    try:
        cur.execute("SELECT min(id), max(id) FROM whatsapp_raw_payloads")
        lo_all, hi_all = cur.fetchone()

        if lo_all is not None and hi_all is not None:
            dt_min = datetime.combine(data_inicial - timedelta(days=2), datetime.min.time())
            dt_max = datetime.combine(data_final + timedelta(days=7), datetime.max.time())
            min_wrp = _find_wrp_id_bound(cur, lo_all, hi_all, dt_min, is_min=True)
            max_wrp = _find_wrp_id_bound(cur, lo_all, hi_all, dt_max, is_min=False)

            # 1) Paginação em lotes de WRP_PAGE_SIZE pelo índice primário de whatsapp_raw_payloads
            for start_id in range(min_wrp, max_wrp + 1, WRP_PAGE_SIZE):
                end_id = min(max_wrp, start_id + WRP_PAGE_SIZE - 1)
                cur.execute(
                    """
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
                        t.name AS team,
                        ct.phone_number AS phone_number,
                        c.custom_attributes,
                        entry->'changes'->0->'value'->'messages'->0->'referral'->>'source_id' AS source_id,
                        fc.nome_campanha,
                        fc.nome_anuncio,
                        c.status
                    FROM whatsapp_raw_payloads wrp
                    JOIN messages m ON m.source_id = wrp.source_id
                    JOIN conversations c ON c.id = m.conversation_id
                    CROSS JOIN LATERAL jsonb_array_elements(wrp.payload->'entry') AS entry
                    LEFT JOIN contacts ct ON ct.id = c.contact_id
                    LEFT JOIN users u ON u.id = c.assignee_id
                    LEFT JOIN team_members tm ON tm.user_id = u.id
                    LEFT JOIN teams t ON t.id = tm.team_id
                    LEFT JOIN facebook_campanhas fc
                        ON fc.source_id = entry->'changes'->0->'value'->'messages'->0->'referral'->>'source_id'
                    WHERE wrp.id BETWEEN %s AND %s
                        AND wrp.source_id IS NOT NULL
                        AND c.created_at::date >= %s
                        AND c.created_at::date <= %s
                        AND (
                            entry->'changes'->0->'value'->'messages'->0->'referral' IS NOT NULL
                            OR
                            c.custom_attributes->>'link_campanha' IS NOT NULL
                        )
                    ORDER BY m.conversation_id, c.created_at, t.name
                    """,
                    (start_id, end_id, data_inicial, data_final),
                )
                for row in cur.fetchall():
                    conv_id = row[0]
                    if conv_id not in by_conv:
                        by_conv[conv_id] = row
                    elif not by_conv[conv_id][10] and row[10]:
                        by_conv[conv_id] = row

        # 2) Paginação em lotes de CONV_PAGE_SIZE para conversas com link_campanha em custom_attributes
        offset = 0
        while True:
            cur.execute(
                """
                SELECT DISTINCT ON (c.id)
                    c.id AS conversation_id,
                    c.account_id,
                    c.created_at,
                    c.custom_attributes->>'link_campanha' AS link_campanha,
                    NULL AS id_campanha,
                    c.custom_attributes->>'evento_nbs' AS link_crm,
                    u.name AS responsavel,
                    t.name AS team,
                    ct.phone_number AS phone_number,
                    c.custom_attributes,
                    NULL AS source_id,
                    NULL AS nome_campanha,
                    NULL AS nome_anuncio,
                    c.status
                FROM conversations c
                JOIN messages m ON m.conversation_id = c.id
                LEFT JOIN contacts ct ON ct.id = c.contact_id
                LEFT JOIN users u ON u.id = c.assignee_id
                LEFT JOIN team_members tm ON tm.user_id = u.id
                LEFT JOIN teams t ON t.id = tm.team_id
                WHERE c.created_at::date >= %s
                    AND c.created_at::date <= %s
                    AND c.custom_attributes->>'link_campanha' IS NOT NULL
                ORDER BY c.id, c.created_at, t.name
                LIMIT %s OFFSET %s
                """,
                (data_inicial, data_final, CONV_PAGE_SIZE, offset),
            )
            rows = cur.fetchall()
            if not rows:
                break
            for row in rows:
                conv_id = row[0]
                if conv_id not in by_conv:
                    by_conv[conv_id] = row
            if len(rows) < CONV_PAGE_SIZE:
                break
            offset += CONV_PAGE_SIZE

    finally:
        cur.close()
        conn.close()

    sorted_rows = [by_conv[k] for k in sorted(by_conv.keys())]
    return pd.DataFrame(sorted_rows, columns=columns)


def _fetch_oracle_eventos_paginated(lista_eventos):
    columns_default = ["evento", "responsavel_oracle", "andamento_atendimento", "termometro", "cod_proposta", "descricao_midia"]
    if not lista_eventos:
        return pd.DataFrame(columns=columns_default)

    all_rows = []
    columns_oracle = columns_default
    conn_oracle, cur_oracle = oracle()
    try:
        for i in range(0, len(lista_eventos), ORACLE_PAGE_SIZE):
            batch = lista_eventos[i : i + ORACLE_PAGE_SIZE]
            in_clause = ",".join(f"'{e}'" for e in batch)
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
                ce.COD_PROPOSTA,
                M.DESCRICAO AS descricao_midia
            FROM crm_eventos ce
            LEFT JOIN empresas_usuarios eu ON 1=1
                AND eu.nome = ce.RESPONSAVEL_PELO_EVENTO
            LEFT JOIN CRM_ANDAMENTO ca ON 1=1
                AND ca.COD_ANDAMENTO = ce.COD_ANDAMENTO
            LEFT JOIN midia m ON 1=1
                AND m.cod_midia = ce.cod_midia
            WHERE concat(ce.COD_EMPRESA, ce.COD_EVENTO) IN ({in_clause})
            """
            cur_oracle.execute(query_oracle_eventos)
            rows = cur_oracle.fetchall()
            if cur_oracle.description:
                columns_oracle = [desc[0].lower() for desc in cur_oracle.description]
            all_rows.extend(rows)
    finally:
        cur_oracle.close()
        conn_oracle.close()

    if not all_rows:
        return pd.DataFrame(columns=columns_oracle)
    return pd.DataFrame(all_rows, columns=columns_oracle, dtype=str).fillna("")


def build_fechamento_leads_excel(data_inicial, data_final):
    df_chatwoot = _fetch_chatwoot_paginated(data_inicial, data_final)
    df_chatwoot = df_chatwoot.fillna("").replace("None", "")

    if df_chatwoot.empty:
        df_export = pd.DataFrame()
    else:
        df_chatwoot["ddd"] = df_chatwoot["phone_number"].apply(extrair_ddd)
        df_chatwoot["link_chat"] = df_chatwoot.apply(
            lambda row: f"https://chat.caiuas.com.br/app/accounts/{row['account_id']}/conversations/{row['conversation_id']}"
            if str(row.get("account_id", "")).strip() != "" and str(row.get("conversation_id", "")).strip() != ""
            else "",
            axis=1,
        )

        df_chatwoot_excel = df_chatwoot[
            [
                "conversation_id",
                "responsavel",
                "team",
                "ddd",
                "created_at",
                "nome_campanha",
                "nome_anuncio",
                "link_campanha",
                "source_id",
                "link_crm",
                "link_chat",
                "status",
            ]
        ].copy()

        df_chatwoot_excel["evento"] = df_chatwoot_excel["link_crm"].apply(
            lambda x: str(x).split("?")[0] if str(x).strip() != "" else ""
        )
        df_chatwoot_excel["evento"] = df_chatwoot_excel["evento"].apply(
            lambda x: str(x).split("/")[-1] if str(x).strip() != "" else ""
        )

        lista_eventos_oracle = [
            e for e in df_chatwoot_excel["evento"].unique() if str(e).strip() != "" and str(e).strip().isdigit()
        ]

        if lista_eventos_oracle:
            try:
                df_oracle_eventos = _fetch_oracle_eventos_paginated(lista_eventos_oracle)
                df_chatwoot_excel = df_chatwoot_excel.merge(
                    df_oracle_eventos[
                        ["evento", "andamento_atendimento", "termometro", "cod_proposta", "descricao_midia"]
                    ],
                    on="evento",
                    how="left",
                )
                df_chatwoot_excel["andamento_atendimento"] = df_chatwoot_excel["andamento_atendimento"].fillna("")
                df_chatwoot_excel["cod_proposta"] = df_chatwoot_excel["cod_proposta"].fillna("")
                df_chatwoot_excel["termometro"] = df_chatwoot_excel["termometro"].apply(
                    lambda v: "Não classificado" if pd.isna(v) or str(v).strip() in ("", "None") else str(v).strip()
                )
                df_chatwoot_excel["termometro"] = df_chatwoot_excel.apply(
                    lambda row: "Não classificado"
                    if str(row["andamento_atendimento"]).strip() == "" and str(row["cod_proposta"]).strip() != ""
                    else row["termometro"],
                    axis=1,
                )
                df_chatwoot_excel["andamento_atendimento"] = df_chatwoot_excel["andamento_atendimento"].apply(
                    lambda v: "Pendente" if pd.isna(v) or str(v).strip() in ("", "None") else str(v).strip()
                )
                df_chatwoot_excel["descricao_midia"] = df_chatwoot_excel["descricao_midia"].apply(
                    lambda v: "" if pd.isna(v) or str(v).strip() in ("", "None") else str(v).strip()
                )
            except Exception as exc:
                logger.error("Erro ao consultar eventos no Oracle NBS: %s", exc)
                df_chatwoot_excel["andamento_atendimento"] = ""
                df_chatwoot_excel["termometro"] = "Não classificado"
                df_chatwoot_excel["cod_proposta"] = ""
                df_chatwoot_excel["descricao_midia"] = ""
        else:
            df_chatwoot_excel["andamento_atendimento"] = ""
            df_chatwoot_excel["termometro"] = "Não classificado"
            df_chatwoot_excel["cod_proposta"] = ""
            df_chatwoot_excel["descricao_midia"] = ""

        status_col = df_chatwoot_excel.get("status", pd.Series("", index=df_chatwoot_excel.index))
        link_crm_col = df_chatwoot_excel.get("link_crm", pd.Series("", index=df_chatwoot_excel.index))
        mask_status_descartado = status_col.apply(lambda v: str(v).strip() in ("1", "1.0"))
        mask_sem_evento_nbs = link_crm_col.apply(lambda v: pd.isna(v) or str(v).strip() in ("", "None"))
        df_chatwoot_excel.loc[mask_status_descartado & mask_sem_evento_nbs, "termometro"] = "Descartado"

        mask_termometro_descartado = df_chatwoot_excel["termometro"].apply(
            lambda v: str(v).strip().lower() == "descartado"
        )
        df_chatwoot_excel.loc[mask_sem_evento_nbs & mask_termometro_descartado, "andamento_atendimento"] = "Descartado"

        mask_termometro_nao_classificado = df_chatwoot_excel["termometro"].apply(
            lambda v: str(v).strip().lower() in ("não classificado", "nao classificado")
        )
        mask_andamento_pendente = df_chatwoot_excel["andamento_atendimento"].apply(
            lambda v: str(v).strip().lower() == "pendente"
        )
        df_chatwoot_excel.loc[
            mask_sem_evento_nbs & mask_termometro_nao_classificado & mask_andamento_pendente,
            "andamento_atendimento",
        ] = "Outros assuntos"

        df_export = df_chatwoot_excel.drop(columns=["link_crm", "link_chat", "status"], errors="ignore").copy()
        if "created_at" in df_export.columns:
            df_export["created_at"] = pd.to_datetime(df_export["created_at"], errors="coerce").dt.tz_localize(None)

    total_linhas = len(df_export)
    excel_buffer = io.BytesIO()

    with pd.ExcelWriter(excel_buffer, engine="xlsxwriter") as writer:
        workbook = writer.book
        if df_export.empty:
            worksheet = workbook.add_worksheet("Chatwoot")
            worksheet.write("A1", "Sem conversões no periodo")
        else:
            df_export.to_excel(writer, index=False, sheet_name="Chatwoot", startrow=1)
            worksheet = writer.sheets["Chatwoot"]

            worksheet.set_row(0, 50)
            for logo_path in LOGO_CANDIDATES:
                if os.path.exists(logo_path):
                    try:
                        worksheet.insert_image(
                            "A1",
                            logo_path,
                            {"x_scale": 0.6, "y_scale": 0.6, "x_offset": 5, "y_offset": 5},
                        )
                        break
                    except Exception:
                        pass

            title_format = workbook.add_format(
                {
                    "bold": True,
                    "font_size": 32,
                    "align": "center",
                    "valign": "vcenter",
                    "font_name": "Calibri",
                }
            )

            max_col_index = len(df_export.columns) - 1
            if max_col_index >= 1:
                worksheet.merge_range(0, 1, 0, max_col_index, "Leads Caiuás", title_format)
            else:
                worksheet.write(0, 1, "Leads Caiuás", title_format)

            datetime_format = workbook.add_format({"num_format": "dd/mm/yyyy hh:mm"})

            for i, col in enumerate(df_export.columns):
                series_len = df_export[col].fillna("").astype(str).map(len)
                max_len = int(max(series_len.max() if not series_len.empty else 0, len(str(col))) + 2)
                if col == "created_at":
                    worksheet.set_column(i, i, max(max_len, 18), datetime_format)
                else:
                    worksheet.set_column(i, i, max_len)

            max_row, max_col = df_export.shape
            column_settings = [{"header": str(col)} for col in df_export.columns]
            worksheet.add_table(
                1,
                0,
                max_row + 1,
                max_col - 1,
                {
                    "columns": column_settings,
                    "name": "Atendimentos",
                    "style": "Table Style Light 1",
                },
            )

    excel_buffer.seek(0)
    filename = f"fechamento_leads_agencia_{data_inicial.strftime('%Y%m%d')}_{data_final.strftime('%Y%m%d')}.xlsx"
    return excel_buffer.getvalue(), filename, total_linhas


@app.task(bind=True, max_retries=1, default_retry_delay=30)
def gerar_fechamento_leads_agencia(self, chat_id, data_inicial_str, data_final_str):
    logger.info(
        "Iniciando geração paginada de Fechamento Leads Agência para chat_id=%s (%s a %s)",
        chat_id,
        data_inicial_str,
        data_final_str,
    )
    try:
        data_inicial = datetime.strptime(data_inicial_str, "%Y-%m-%d").date()
        data_final = datetime.strptime(data_final_str, "%Y-%m-%d").date()

        excel_bytes, filename, total_linhas = build_fechamento_leads_excel(data_inicial, data_final)
        periodo_fmt = f"{data_inicial.strftime('%d/%m/%Y')} a {data_final.strftime('%d/%m/%Y')}"
        caption = f"Fechamento Leads Agência ({periodo_fmt}) — {total_linhas} linhas"

        sent = _send_telegram_document(chat_id, filename, excel_bytes, caption=caption)
        return {"status": "success" if sent else "send_error", "rows": total_linhas, "file": filename}
    except Exception as exc:
        logger.exception("Erro ao gerar Fechamento Leads Agência: %s", exc)
        _send_telegram_message(chat_id, f"Não foi possível gerar o relatório Fechamento Leads Agência: {exc}")
        return {"status": "error", "error": str(exc)}
