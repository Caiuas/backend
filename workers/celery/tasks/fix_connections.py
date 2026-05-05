import os
import logging
from dotenv import load_dotenv
from app import app
from database import oracle

load_dotenv()

logger = logging.getLogger(__name__)

TIMEOUT_SEGUNDOS = int(os.getenv("NBS_INACTIVE_TIMEOUT", "300"))


def _fetch_inactive(cursor):
    query = """
        SELECT sid, serial#, last_call_et
        FROM v$session
        WHERE program = 'JDBC Thin Client'
          AND status = 'INACTIVE'
          AND last_call_et > ?
    """
    cursor.execute(query, [TIMEOUT_SEGUNDOS])
    return cursor.fetchall()


def _kill_session(cursor, sid, serial):
    sql = f"ALTER SYSTEM KILL SESSION '{sid},{serial}' IMMEDIATE"
    cursor.execute(sql)


@app.task(bind=True, max_retries=2, default_retry_delay=120)
def fix_connections_nbs(self):
    conn = None
    cursor = None

    try:
        conn, cursor = oracle()
        sessions = _fetch_inactive(cursor)

        if not sessions:
            logger.info("fix_connections_nbs: nenhuma sessao JDBC inativa > %ds", TIMEOUT_SEGUNDOS)
            return {"killed": 0}

        mortas = 0
        for sid, serial, last_call_et in sessions:
            try:
                _kill_session(cursor, sid, serial)
                logger.warning(
                    "fix_connections_nbs: sessao %s,%s encerrada (inativa ha %ds)",
                    sid, serial, last_call_et,
                )
                mortas += 1
            except Exception as exc:
                logger.error("fix_connections_nbs: erro ao matar %s,%s: %s", sid, serial, exc)

        return {"killed": mortas, "checked": len(sessions)}

    except Exception as exc:
        logger.error("fix_connections_nbs: falha na execucao: %s", exc)
        try:
            self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            logger.critical("fix_connections_nbs: max retries excedido, pulando esta execucao")
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
        if conn:
            try:
                conn.close()
            except Exception:
                pass
