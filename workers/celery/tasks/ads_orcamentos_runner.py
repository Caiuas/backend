import logging
import subprocess
import sys

from app import app

logger = logging.getLogger(__name__)


@app.task(bind=True, name="tasks.ads_orcamentos_runner.run_ads_orcamentos_module")
def run_ads_orcamentos_module(self):
    cmd = [sys.executable, "-m", "tasks.ads_orcamentos"]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        logger.error("ads_orcamentos falhou (exit=%s)", result.returncode)
        if result.stdout:
            logger.error("stdout: %s", result.stdout[-1000:])
        if result.stderr:
            logger.error("stderr: %s", result.stderr[-1000:])
        raise RuntimeError(f"Falha ao executar {' '.join(cmd)}")

    if result.stdout:
        logger.info("ads_orcamentos stdout: %s", result.stdout[-1000:])

    return {"status": "ok", "command": " ".join(cmd)}
