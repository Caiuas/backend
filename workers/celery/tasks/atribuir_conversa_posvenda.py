import logging
import os
import time

import requests
from celery.signals import worker_ready
from dotenv import load_dotenv

from app import app

load_dotenv()

logger = logging.getLogger(__name__)

AGENTES_POSVENDA = [149, 74]
INBOX_ID = 1
CONTA_ID = 1
INTERVALO_SEGUNDOS = 1
BASE_URL = "https://chat.caiuas.com.br/api/v1/accounts"


def _headers():
    return {
        "api_access_token": os.getenv("CHATWOOT_TOKEN"),
        "Content-Type": "application/json",
    }


def _buscar_conversas_nao_atribuidas():
    url = (
        f"{BASE_URL}/{CONTA_ID}/conversations"
        f"?status=open&assignee_type=unassigned&inbox_id={INBOX_ID}"
    )
    response = requests.request("GET", url, headers=_headers(), data={})
    response.raise_for_status()
    body = response.json()
    payload = body.get("data", {}).get("payload", [])
    return [conversa["id"] for conversa in payload if conversa.get("id")]


def _atribuir_conversa(conversation_id, assignee_id):
    url = f"{BASE_URL}/{CONTA_ID}/conversations/{conversation_id}/assignments"
    payload = {"assignee_id": assignee_id}
    response = requests.request("POST", url, headers=_headers(), json=payload)
    response.raise_for_status()
    return response


@app.task(
    bind=True,
    name="tasks.atribuir_conversa_posvenda.atribuir_conversa_posvenda",
    acks_late=True,
)
def atribuir_conversa_posvenda(self):
    indice_agente = 0

    logger.info(
        "atribuir_conversa_posvenda: iniciando loop (agentes=%s, intervalo=%ss)",
        AGENTES_POSVENDA,
        INTERVALO_SEGUNDOS,
    )

    while True:
        try:
            conversas = _buscar_conversas_nao_atribuidas()

            if conversas:
                logger.info(
                    "atribuir_conversa_posvenda: %s conversa(s) sem atribuicao",
                    len(conversas),
                )

            for conversation_id in conversas:
                assignee_id = AGENTES_POSVENDA[indice_agente % len(AGENTES_POSVENDA)]
                try:
                    _atribuir_conversa(conversation_id, assignee_id)
                    logger.info(
                        "atribuir_conversa_posvenda: conversa %s atribuida ao agente %s",
                        conversation_id,
                        assignee_id,
                    )
                    indice_agente += 1
                except Exception as exc:
                    logger.error(
                        "atribuir_conversa_posvenda: erro ao atribuir conversa %s: %s",
                        conversation_id,
                        exc,
                    )

        except Exception as exc:
            logger.exception("atribuir_conversa_posvenda: falha na execucao: %s", exc)

        time.sleep(INTERVALO_SEGUNDOS)


@worker_ready.connect
def _iniciar_atribuir_conversa_posvenda(**kwargs):
    atribuir_conversa_posvenda.delay()
