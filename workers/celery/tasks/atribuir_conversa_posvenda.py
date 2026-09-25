import fcntl
import json
import logging
import os
import time

import requests
from dotenv import load_dotenv

from app import app

load_dotenv()

logger = logging.getLogger(__name__)

AGENTES_POSVENDA = [117]
INBOX_ID = 1
CONTA_ID = 1
BASE_URL = "https://chat.caiuas.com.br/api/v1/accounts"
JANELA_IGNORAR_SEGUNDOS = 120
HTTP_TIMEOUT = 10

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
ESTADO_FILE = os.path.join(_DATA_DIR, "atribuir_conversa_posvenda.json")
RECENTES_FILE = os.path.join(_DATA_DIR, "atribuir_conversa_posvenda_recentes.json")
LOCK_FILE = os.path.join(_DATA_DIR, "atribuir_conversa_posvenda.lock")


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


def _carregar_recentes():
    """Dicionario persistente {conversation_id: timestamp}.

    Precisa ser em disco (e nao so memoria) porque o Celery usa
    ForkPoolWorker: cada worker-filho tem sua propria memoria.
    """
    try:
        with open(RECENTES_FILE, "r") as arquivo:
            dados = json.load(arquivo)
        if isinstance(dados, dict):
            agora = time.time()
            return {
                str(cid): ts
                for cid, ts in dados.items()
                if isinstance(ts, (int, float))
                and agora - ts <= JANELA_IGNORAR_SEGUNDOS
            }
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return {}


def _salvar_recentes(recentes):
    os.makedirs(os.path.dirname(RECENTES_FILE), exist_ok=True)
    with open(RECENTES_FILE, "w") as arquivo:
        json.dump(recentes, arquivo)


def _adquirir_lock():
    """Lock nao-bloqueante entre processos.

    Garante que, se a execucao anterior (tick de 2s) ainda estiver
    rodando, o novo tick encerra imediatamente com already_running
    em vez de processar as mesmas conversas em duplicidade.
    O lock e liberado no finally, inclusive em caso de excecao.
    """
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
    response = requests.request("GET", url, headers=_headers(), data={}, timeout=HTTP_TIMEOUT)
    response.raise_for_status()
    body = response.json()
    payload = body.get("data", {}).get("payload", [])
    return [conversa["id"] for conversa in payload if conversa.get("id")]


def _conversa_estah_livre(conversation_id):
    url = f"{BASE_URL}/{CONTA_ID}/conversations/{conversation_id}"
    response = requests.request("GET", url, headers=_headers(), data={}, timeout=HTTP_TIMEOUT)
    response.raise_for_status()
    conversa = response.json()
    assignee = (conversa.get("meta") or {}).get("assignee")
    if not assignee:
        return True, None
    return False, assignee.get("id")


def _atribuir_conversa(conversation_id, assignee_id):
    url = f"{BASE_URL}/{CONTA_ID}/conversations/{conversation_id}/assignments"
    payload = {"assignee_id": assignee_id}
    response = requests.request("POST", url, headers=_headers(), json=payload, timeout=HTTP_TIMEOUT)
    response.raise_for_status()
    return response


@app.task(
    bind=True,
    name="tasks.atribuir_conversa_posvenda.atribuir_conversa_posvenda",
    max_retries=0,
    time_limit=30,
    soft_time_limit=25,
)
def atribuir_conversa_posvenda(self):
    """Uma passada curta, chamada pelo beat a cada 2s.

    Nao ha loop interno: cada tick faz no maximo 1 varredura e sai
    em segundos, entao nunca segura mensagem sem ack por 30min
    (causa do 406 PRECONDITION_FAILED anterior).
    """
    lock = _adquirir_lock()
    if lock is None:
        logger.warning(
            "atribuir_conversa_posvenda: tick anterior ainda em execucao; "
            "pulando este tick para nao duplicar"
        )
        return {"status": "already_running"}

    try:
        indice_agente = _carregar_indice()
        recentes = _carregar_recentes()

        try:
            conversas = _buscar_conversas_nao_atribuidas()
        except Exception as exc:
            logger.exception("atribuir_conversa_posvenda: falha ao listar conversas: %s", exc)
            raise

        if not conversas:
            return {"status": "no_pending"}

        logger.info(
            "atribuir_conversa_posvenda: %s conversa(s) sem atribuicao",
            len(conversas),
        )

        atribuidas = 0
        ignoradas = 0

        for conversation_id in conversas:
            cid_str = str(conversation_id)
            if cid_str in recentes:
                logger.info(
                    "atribuir_conversa_posvenda: conversa %s atribuida "
                    "recentemente; ignorando",
                    conversation_id,
                )
                ignoradas += 1
                continue

            assignee_id = AGENTES_POSVENDA[indice_agente % len(AGENTES_POSVENDA)]

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
                ignoradas += 1
                continue

            try:
                _atribuir_conversa(conversation_id, assignee_id)
                logger.info(
                    "atribuir_conversa_posvenda: conversa %s atribuida ao "
                    "agente %s",
                    conversation_id,
                    assignee_id,
                )
                recentes[cid_str] = time.time()
                _salvar_recentes(recentes)
                indice_agente = (indice_agente + 1) % len(AGENTES_POSVENDA)
                _salvar_indice(indice_agente)
                atribuidas += 1
            except Exception as exc:
                logger.error(
                    "atribuir_conversa_posvenda: erro ao atribuir conversa "
                    "%s: %s",
                    conversation_id,
                    exc,
                )

        return {"status": "ok", "atribuidas": atribuidas, "ignoradas": ignoradas}
    finally:
        _liberar_lock(lock)
