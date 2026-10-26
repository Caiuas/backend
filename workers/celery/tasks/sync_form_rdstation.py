import argparse
import base64
import json
import logging
import os
import sys
from datetime import datetime
from urllib.parse import parse_qs, urlparse

import requests
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import app
from database import oracle

load_dotenv()

logger = logging.getLogger(__name__)

RDSTATION_AUTH_URL = "https://api.rd.services/auth/token"
RDSTATION_API_BASE = "https://api.rd.services/platform"
SEGMENTATION_ID = "20259909"

TOKENS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "rdstation_tokens_caiuas.json"
)

PAGE_SIZE = 100
MAX_PAGES = 1000

COD_EMPRESA = 11
COD_TIPO_EVENTO = 841
COD_ANDAMENTO = 2
COD_PRIORIDADE = 2
COD_CLIENTE_AVULSO = 1
CRIOU_O_EVENTO = "RDSTATION"

ALLOWED_EVENT_IDENTIFIERS = {
    "Outubro - V1",
}
ALLOWED_EVENT_IDENTIFIERS_NORMALIZED = {
    value.strip().casefold() for value in ALLOWED_EVENT_IDENTIFIERS
}


def _carregar_tokens():
    try:
        with open(TOKENS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _salvar_tokens(tokens):
    os.makedirs(os.path.dirname(TOKENS_FILE), exist_ok=True)
    with open(TOKENS_FILE, "w", encoding="utf-8") as f:
        json.dump(tokens, f)


def _request_token(refresh_token):
    return requests.post(
        RDSTATION_AUTH_URL,
        json={
            "client_id": os.getenv("RDSTATION_CLIENT_ID_CAIUAS"),
            "client_secret": os.getenv("RDSTATION_CLIENT_SECRET_CAIUAS"),
            "refresh_token": refresh_token,
        },
        headers={"Content-Type": "application/json"},
        timeout=30,
    )


def get_access_token():
    tokens = _carregar_tokens()

    refresh_candidates = []
    for refresh_token in (
        tokens.get("refresh_token"),
        os.getenv("RDSTATION_REFRESH_TOKEN_CAIUAS"),
    ):
        if refresh_token and refresh_token not in refresh_candidates:
            refresh_candidates.append(refresh_token)

    if not refresh_candidates:
        raise RuntimeError(
            "Refresh token do RD Station Caiuás não encontrado no arquivo de tokens nem no .env"
        )

    last_error = None
    for refresh_token in refresh_candidates:
        response = _request_token(refresh_token)
        if response.status_code == 200:
            data = response.json()
            tokens["access_token"] = data.get("access_token")
            tokens["refresh_token"] = data.get("refresh_token", refresh_token)
            _salvar_tokens(tokens)
            return tokens["access_token"]

        last_error = response.text
        logger.warning(
            "sync_form_rdstation: falha ao renovar token com refresh_token %s...: %s",
            refresh_token[:8],
            response.text,
        )

    raise RuntimeError(f"Não foi possível obter access_token do RD Station: {last_error}")


def _headers(access_token):
    return {"Authorization": f"Bearer {access_token}"}


def _api_get(url, access_token, params=None):
    return requests.get(
        url, headers=_headers(access_token), params=params, timeout=60
    )


def fetch_contact(contact_uuid, access_token):
    response = _api_get(
        f"{RDSTATION_API_BASE}/contacts/{contact_uuid}", access_token
    )
    response.raise_for_status()
    return response.json()


def iter_contacts(access_token):
    page = 1
    while page <= MAX_PAGES:
        response = _api_get(
            f"{RDSTATION_API_BASE}/segmentations/{SEGMENTATION_ID}/contacts",
            access_token,
            params={"page": page, "page_size": PAGE_SIZE},
        )
        response.raise_for_status()

        data = response.json()
        contacts = data.get("contacts") or []
        if not contacts:
            break

        for contact in contacts:
            yield contact

        if len(contacts) < PAGE_SIZE:
            break

        page += 1


def fetch_conversion_events(contact_uuid, access_token):
    response = _api_get(
        f"{RDSTATION_API_BASE}/contacts/{contact_uuid}/events",
        access_token,
        params={"event_type": "CONVERSION"},
    )
    response.raise_for_status()

    data = response.json()
    if isinstance(data, list):
        return data
    return data.get("events") or []


def _event_key(event):
    key = "".join(
        str(event.get(field) or "")
        for field in (
            "event_type",
            "event_family",
            "event_identifier",
            "event_timestamp",
        )
    )
    return key[:4000]


def _first_value(*values):
    for value in values:
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _event_datetime(event):
    timestamp = event.get("event_timestamp")
    if not timestamp:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        dt = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _utm_source_from_traffic_source(traffic_source):
    if not traffic_source:
        return None

    text = str(traffic_source).strip()
    if not text:
        return None

    if text.startswith("encoded_"):
        try:
            encoded = text[len("encoded_"):]
            encoded += "=" * (-len(encoded) % 4)
            decoded = base64.b64decode(encoded).decode("utf-8")
            data = json.loads(decoded)
            for session_key in ("current_session", "first_session"):
                session = data.get(session_key) or {}
                session_value = session.get("value")
                if session_value:
                    qs = parse_qs(session_value)
                    if qs.get("utm_source"):
                        return qs["utm_source"][0]
        except Exception:
            pass

    parsed = urlparse(text)
    query = parsed.query if parsed.query else text
    qs = parse_qs(query)
    if qs.get("utm_source"):
        return qs["utm_source"][0]

    return None


def _extract_utm_source(payload):
    return _first_value(
        payload.get("utm_source"),
        _utm_source_from_traffic_source(payload.get("traffic_source")),
    )


def _build_observacao(contact, event):
    payload = event.get("payload") or {}
    tags = payload.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]

    linhas = [
        "Evento importado automaticamente do RD Station",
        f"Contato UUID: {contact.get('uuid')}",
        f"Contato nome: {contact.get('name')}",
        f"Contato email: {contact.get('email')}",
        f"Contato telefone: {_first_value(contact.get('mobile_phone'), contact.get('phone'))}",
        f"event_type: {event.get('event_type')}",
        f"event_family: {event.get('event_family')}",
        f"event_identifier: {event.get('event_identifier')}",
        f"event_timestamp: {event.get('event_timestamp')}",
        f"conversion_identifier: {payload.get('conversion_identifier')}",
        f"tags: {', '.join(str(tag) for tag in tags)}",
        f"traffic_source: {payload.get('traffic_source')}",
        f"traffic_medium: {payload.get('traffic_medium')}",
        f"traffic_campaign: {payload.get('traffic_campaign')}",
    ]

    campos_extraidos = []
    for campo in (
        "cf_cidade_forms",
        "cf_busca_modelo_forms",
        "cf_troca_veiculo_forms",
    ):
        valor = _first_value(payload.get(campo))
        if valor:
            campos_extraidos.append(f"{campo}: {valor}")

    utm_source = _extract_utm_source(payload)
    if utm_source:
        campos_extraidos.append(f"utm_source: {utm_source}")

    if campos_extraidos:
        linhas.append("--- Campos extraídos do payload ---")
        linhas.extend(campos_extraidos)

    linhas.append(
        "payload_json: " + json.dumps(payload, ensure_ascii=False, sort_keys=True)
    )
    linhas.append(
        "event_json: " + json.dumps(event, ensure_ascii=False, sort_keys=True)
    )
    return "\n".join(linhas)


def _insert_event(cur, contact, event, dry_run=False):
    event_key = _event_key(event)

    cur.execute(
        "SELECT COUNT(*) FROM crm_eventos WHERE COD_EMPRESA = ? AND OBS_DIVERSO = ?",
        [COD_EMPRESA, event_key],
    )
    if cur.fetchone()[0] > 0:
        return {"status": "duplicate", "event_key": event_key}

    payload = event.get("payload") or {}
    nome = _first_value(
        payload.get("name"),
        contact.get("name"),
        f"Contato RD Station {contact.get('uuid')}",
    )
    email = _first_value(payload.get("email"), contact.get("email"))
    fone = _first_value(
        payload.get("mobile_phone"),
        payload.get("phone"),
        contact.get("mobile_phone"),
        contact.get("phone"),
    )
    data_evento = _event_datetime(event)
    observacao = _build_observacao(contact, event)

    event_identifier = _first_value(event.get("event_identifier"), "CONVERSION")
    desc_evento = f"RD Station: {event_identifier} - {nome or email or ''}"[:200]

    cur.execute("SELECT seq_crm_COD_EVENTO.nextval FROM dual")
    cod_evento = cur.fetchone()[0]

    cur.execute(
        """
        INSERT INTO crm_eventos (
            COD_EMPRESA,
            COD_EVENTO,
            COD_TIPO_EVENTO,
            COD_PRIORIDADE,
            NOME_CLIENTE_AVULSO,
            FONE_CLIENTE_AVULSO,
            COD_MIDIA,
            DATA_CRIACAO,
            COD_CLIENTE_HONDA,
            DESC_EVENTO,
            CRIOU_O_EVENTO,
            DATA_EVENTO,
            OBS_MEMO,
            COD_ANDAMENTO,
            COD_CLIENTE,
            STATUS,
            RESPONSAVEL_PELO_EVENTO,
            TIPO_ATENDIMENTO,
            COD_PRODUTO,
            COD_MODELO,
            EMAIL_CLIENTE_AVULSO,
            OBS_DIVERSO
        ) VALUES (
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            NULL,
            TO_DATE(?, 'YYYY-MM-DD HH24:MI:SS'),
            seq_cod_cliente_honda.nextval,
            ?,
            ?,
            TO_DATE(?, 'YYYY-MM-DD HH24:MI:SS'),
            ?,
            ?,
            ?,
            'P',
            NULL,
            NULL,
            NULL,
            NULL,
            ?,
            ?
        )
        """,
        [
            COD_EMPRESA,
            cod_evento,
            COD_TIPO_EVENTO,
            COD_PRIORIDADE,
            nome,
            fone,
            data_evento,
            desc_evento,
            CRIOU_O_EVENTO,
            data_evento,
            observacao,
            COD_ANDAMENTO,
            COD_CLIENTE_AVULSO,
            email,
            event_key,
        ],
    )

    return {
        "status": "dry_run" if dry_run else "inserted",
        "cod_evento": cod_evento,
        "cod_evento_completo": f"{COD_EMPRESA}{cod_evento}",
        "event_key": event_key,
    }


def run_sync(contact_uuid=None, dry_run=False):
    access_token = get_access_token()
    conn = None
    cur = None

    stats = {
        "contacts": 0,
        "events": 0,
        "inserted": 0,
        "duplicates": 0,
        "ignored": 0,
        "errors": 0,
        "dry_run": dry_run,
        "eventos": [],
    }

    try:
        conn, cur = oracle()

        if contact_uuid:
            contacts = [fetch_contact(contact_uuid, access_token)]
        else:
            contacts = iter_contacts(access_token)

        for contact in contacts:
            stats["contacts"] += 1
            contact_uuid_atual = contact.get("uuid")

            try:
                events = fetch_conversion_events(contact_uuid_atual, access_token)
            except Exception as exc:
                stats["errors"] += 1
                logger.error(
                    "sync_form_rdstation: erro ao buscar eventos do contato %s: %s",
                    contact_uuid_atual,
                    exc,
                )
                continue

            stats["events"] += len(events)

            for event in events:
                event_identifier = str(event.get("event_identifier") or "").strip()
                if event_identifier.casefold() not in ALLOWED_EVENT_IDENTIFIERS_NORMALIZED:
                    stats["ignored"] += 1
                    logger.info(
                        "sync_form_rdstation: event_identifier fora da whitelist: %s",
                        event_identifier,
                    )
                    continue

                try:
                    resultado = _insert_event(cur, contact, event, dry_run=dry_run)
                    if resultado["status"] == "duplicate":
                        stats["duplicates"] += 1
                        logger.info(
                            "sync_form_rdstation: evento duplicado ignorado: %s",
                            resultado["event_key"],
                        )
                    else:
                        stats["inserted"] += 1
                        stats["eventos"].append(
                            resultado["cod_evento_completo"]
                        )
                        if not dry_run:
                            conn.jconn.commit()
                        logger.info(
                            "sync_form_rdstation: evento %s %s para o contato %s",
                            resultado["status"],
                            resultado["cod_evento_completo"],
                            contact_uuid_atual,
                        )
                except Exception as exc:
                    stats["errors"] += 1
                    logger.exception(
                        "sync_form_rdstation: erro ao inserir evento do contato %s: %s",
                        contact_uuid_atual,
                        exc,
                    )
                    if not dry_run:
                        conn.jconn.rollback()

        if dry_run:
            conn.jconn.rollback()
            logger.info("sync_form_rdstation: dry-run finalizado, transação revertida")
        else:
            conn.jconn.commit()

        return stats
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


@app.task(bind=True, name="tasks.sync_form_rdstation.sync_form_rdstation")
def sync_form_rdstation(self):
    return run_sync()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Importa conversões do RD Station Caiuás para o crm_eventos"
    )
    parser.add_argument(
        "--contact",
        dest="contact",
        help="UUID de um contato específico para testar",
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="Executa tudo, mas desfaz a transação no final",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    resultado = run_sync(contact_uuid=args.contact, dry_run=args.dry_run)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
