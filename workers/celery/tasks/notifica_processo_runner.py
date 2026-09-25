import logging
import subprocess
import sys

from app import app

logger = logging.getLogger(__name__)


@app.task(bind=True, name="tasks.notifica_processo_runner.run_notifica_processo_module")
def run_notifica_processo_module(self):
    cmd = [sys.executable, "-m", "tasks.notifica_processo"]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        logger.error("notifica_processo falhou (exit=%s)", result.returncode)
        if result.stdout:
            logger.error("stdout: %s", result.stdout[-1000:])
        if result.stderr:
            logger.error("stderr: %s", result.stderr[-1000:])
        raise RuntimeError(f"Falha ao executar {' '.join(cmd)}")

    if result.stdout:
        logger.info("notifica_processo stdout: %s", result.stdout[-1000:])

    return {"status": "ok", "command": " ".join(cmd)}
