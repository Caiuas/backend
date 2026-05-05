import logging
from app import app
from database import oracle

logger = logging.getLogger(__name__)


@app.task(bind=True, max_retries=2, default_retry_delay=60)
def fix_crm_proposta_zero(self):
    conn = None
    cursor = None

    try:
        conn, cursor = oracle()

        sql = "UPDATE crm_eventos SET cod_proposta = NULL WHERE cod_proposta = '0'"
        cursor.execute(sql)
        rows_affected = cursor.rowcount
        conn.jconn.commit()

        logger.info("fix_crm_proposta_zero: %d registro(s) corrigido(s)", rows_affected)
        return {"rows_affected": rows_affected}

    except Exception as exc:
        logger.error("fix_crm_proposta_zero: falha na execucao: %s", exc)
        if conn:
            try:
                conn.jconn.rollback()
            except Exception:
                pass
        raise self.retry(exc=exc)

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
