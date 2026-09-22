import fcntl
import json
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
JANELA_IGNORAR_SEGUNDOS = 120

_atribuidas_recentemente = {}
ESTADO_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "data",
    "atribuir_conversa_posvenda.json",
)
LOCK_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "data",
    "atribuir_conversa_posvenda.lock",
)


def _headers():
    return {
        "api_access_token": os.getenv("CHATWOOT_TOKEN"),
        "Content-Type": "application/json",
    }


def _carregar_indice():
    try:
        with open(ESTADO_FILE, "r") as arquivo:
            estado = json.load(arquivo)
        indice = estado.get("indice_agente")
        if isinstance(indice, int):
            return indice
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return 0


def _salvar_indice(indice):
    os.makedirs(os.path.dirname(ESTADO_FILE), exist_ok=True)
    with open(ESTADO_FILE, "w") as arquivo:
        json.dump({"indice_agente": indice}, arquivo)


def _adquirir_lock():
    os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)
    arquivo = open(LOCK_FILE, "w")
    try:
        fcntl.flock(arquivo, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        arquivo.close()
        return None
    return arquivo


def _liberar_lock(arquivo):
    try:
        fcntl.flock(arquivo, fcntl.LOCK_UN)
    finally:
        arquivo.close()


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


def _conversa_estah_livre(conversation_id):
    url = f"{BASE_URL}/{CONTA_ID}/conversations/{conversation_id}"
    response = requests.request("GET", url, headers=_headers(), data={})
    response.raise_for_status()
    conversa = response.json()
    assignee = (conversa.get("meta") or {}).get("assignee")
    if not assignee:
        return True, None
    return False, assignee.get("id")


def _foi_atribuida_recentemente(conversation_id):
    agora = time.time()
    for cid in list(_atribuidas_recentemente):
        if agora - _atribuidas_recentemente[cid] > JANELA_IGNORAR_SEGUNDOS:
            del _atribuidas_recentemente[cid]
    return conversation_id in _atribuidas_recentemente


def _marcar_atribuida(conversation_id):
    _atribuidas_recentemente[conversation_id] = time.time()


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
    lock = _adquirir_lock()
    if lock is None:
        logger.warning(
            "atribuir_conversa_posvenda: ja existe uma instancia em execucao; "
            "encerrando esta instancia"
        )
        return {"status": "already_running"}

    try:
        indice_agente = _carregar_indice()

        logger.info(
            "atribuir_conversa_posvenda: iniciando loop "
            "(agentes=%s, proximo=%s, intervalo=%ss)",
            AGENTES_POSVENDA,
            AGENTES_POSVENDA[indice_agente % len(AGENTES_POSVENDA)],
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
                    if _foi_atribuida_recentemente(conversation_id):
                        logger.info(
                            "atribuir_conversa_posvenda: conversa %s atribuida "
                            "recentemente; ignorando",
                            conversation_id,
                        )
                        continue

                    assignee_id = AGENTES_POSVENDA[
                        indice_agente % len(AGENTES_POSVENDA)
                    ]

                    try:
                        livre, assignee_atual = _conversa_estah_livre(conversation_id)
                    except Exception as exc:
                        logger.error(
                            "atribuir_conversa_posvenda: erro ao verificar conversa "
                            "%s: %s",
                            conversation_id,
                            exc,
                        )
                        continue

                    if not livre:
                        logger.info(
                            "atribuir_conversa_posvenda: conversa %s ja possui "
                            "atribuicao (agente %s); ignorando",
                            conversation_id,
                            assignee_atual,
                        )
                        continue

                    try:
                        _atribuir_conversa(conversation_id, assignee_id)
                        logger.info(
                            "atribuir_conversa_posvenda: conversa %s atribuida ao "
                            "agente %s",
                            conversation_id,
                            assignee_id,
                        )
                        _marcar_atribuida(conversation_id)
                        indice_agente = (indice_agente + 1) % len(AGENTES_POSVENDA)
                        _salvar_indice(indice_agente)
                    except Exception as exc:
                        logger.error(
                            "atribuir_conversa_posvenda: erro ao atribuir conversa "
                            "%s: %s",
                            conversation_id,
                            exc,
                        )

            except Exception as exc:
                logger.exception(
                    "atribuir_conversa_posvenda: falha na execucao: %s", exc
                )

            time.sleep(INTERVALO_SEGUNDOS)
    finally:
        _liberar_lock(lock)


@worker_ready.connect
def _iniciar_atribuir_conversa_posvenda(**kwargs):
    atribuir_conversa_posvenda.delay()
