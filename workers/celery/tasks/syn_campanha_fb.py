import os
import logging
import requests
from dotenv import load_dotenv
from app import app
from database import chatwoot

load_dotenv()

logger = logging.getLogger(__name__)

FB_API = os.getenv("FB_API", "")
FB_GRAPH_URL = "https://graph.facebook.com/v26.0"
FB_FIELDS = "id,name,campaign{id,name}"

QUERY_ULTIMA_CAMPANHA = """
SELECT DISTINCT
    entry->'changes'->0->'value'->'messages'->0->'referral'->>'source_id' AS source_id,
    fc.nome_campanha,
    fc.nome_anuncio,
    m.created_at
FROM messages m
LEFT JOIN whatsapp_raw_payloads wrp ON wrp.source_id = m.source_id
CROSS JOIN LATERAL jsonb_array_elements(wrp.payload->'entry') AS entry
LEFT JOIN conversations c ON c.id = m.conversation_id
LEFT JOIN facebook_campanhas fc
    ON fc.source_id = entry->'changes'->0->'value'->'messages'->0->'referral'->>'source_id'
WHERE entry->'changes'->0->'value'->'messages'->0->'referral'->>'source_id' IS NOT NULL
  AND fc.source_id IS NULL
ORDER BY m.created_at DESC
LIMIT 1
"""


def buscar_ultima_campanha(cursor):
    cursor.execute(QUERY_ULTIMA_CAMPANHA)
    row = cursor.fetchone()
    if not row:
        return None

    return {
        "source_id": row[0],
        "nome_campanha": row[1],
        "nome_anuncio": row[2],
        "created_at": row[3],
    }


def consultar_anuncio(source_id):
    if not FB_API:
        logger.error("syn_campanha_fb: FB_API nao configurado")
        return None

    url = f"{FB_GRAPH_URL}/{source_id}"
    params = {"fields": FB_FIELDS, "access_token": FB_API}

    try:
        response = requests.get(url, params=params, timeout=30)
    except requests.RequestException as exc:
        logger.error("syn_campanha_fb: erro ao consultar anuncio %s: %s", source_id, exc)
        return None

    if response.status_code != 200:
        logger.error(
            "syn_campanha_fb: erro ao consultar anuncio %s - HTTP %s - %s",
            source_id,
            response.status_code,
            response.text[:500],
        )
        return None

    try:
        data = response.json()
    except ValueError:
        logger.error("syn_campanha_fb: resposta invalida para o anuncio %s", source_id)
        return None

    if data.get("error"):
        logger.error("syn_campanha_fb: erro da API para o anuncio %s: %s", source_id, data["error"])
        return None

    nome_anuncio = data.get("name")
    nome_campanha = (data.get("campaign") or {}).get("name")

    if not nome_campanha:
        logger.error("syn_campanha_fb: campanha nao retornada para o anuncio %s", source_id)
        return None

    return nome_campanha, nome_anuncio


def salvar_erro(cursor, source_id):
    cursor.execute(
        "UPDATE facebook_campanhas SET status = 'Erro' WHERE source_id = ?",
        [source_id],
    )

    if cursor.rowcount > 0:
        return "updated"

    cursor.execute(
        """
        INSERT INTO facebook_campanhas (source_id, nome_campanha, nome_anuncio, status)
        VALUES (?, ?, ?, 'Erro')
        """,
        [source_id, "", ""],
    )
    return "inserted"


def salvar_sucesso(cursor, source_id, nome_campanha, nome_anuncio):
    cursor.execute(
        """
        UPDATE facebook_campanhas
        SET nome_campanha = ?, nome_anuncio = ?, status = 'Sucesso'
        WHERE source_id = ?
        """,
        [nome_campanha, nome_anuncio, source_id],
    )

    if cursor.rowcount > 0:
        return "updated"

    cursor.execute(
        """
        INSERT INTO facebook_campanhas (source_id, nome_campanha, nome_anuncio, status)
        VALUES (?, ?, ?, 'Sucesso')
        """,
        [source_id, nome_campanha, nome_anuncio],
    )
    return "inserted"


@app.task(bind=True, max_retries=2, default_retry_delay=120)
def sync_campanha_fb(self):
    conn = None
    cursor = None

    try:
        conn, cursor = chatwoot()
        campanha = buscar_ultima_campanha(cursor)

        if not campanha:
            logger.info("syn_campanha_fb: nenhuma campanha pendente")
            return {"status": "no_pending"}

        source_id = str(campanha["source_id"])
        logger.info("syn_campanha_fb: processando source_id=%s", source_id)

        anuncio = consultar_anuncio(source_id)

        if anuncio is None:
            acao = salvar_erro(cursor, source_id)
            conn.commit()
            logger.warning(
                "syn_campanha_fb: status atualizado para Erro - source_id=%s - acao=%s",
                source_id,
                acao,
            )
            return {"status": "error", "source_id": source_id, "acao": acao}

        nome_campanha, nome_anuncio = anuncio
        acao = salvar_sucesso(cursor, source_id, nome_campanha, nome_anuncio)
        conn.commit()

        logger.info(
            "syn_campanha_fb: status atualizado para Sucesso - source_id=%s - acao=%s",
            source_id,
            acao,
        )
        return {
            "status": "success",
            "source_id": source_id,
            "nome_campanha": nome_campanha,
            "nome_anuncio": nome_anuncio,
            "acao": acao,
        }
    except Exception as exc:
        logger.error("syn_campanha_fb: erro: %s", exc)
        if conn:
            conn.rollback()
        raise self.retry(exc=exc)
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
