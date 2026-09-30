import logging
import subprocess
import sys

from app import app

logger = logging.getLogger(__name__)


@app.task(bind=True, name="tasks.rel_veic_chao_sem_faturar_runner.run_rel_veic_chao_sem_faturar_module")
def run_rel_veic_chao_sem_faturar_module(self):
    cmd = [sys.executable, "-m", "tasks.rel_veic_chao_sem_faturar"]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        logger.error("rel_veic_chao_sem_faturar falhou (exit=%s)", result.returncode)
        if result.stdout:
            logger.error("stdout: %s", result.stdout[-1000:])
        if result.stderr:
            logger.error("stderr: %s", result.stderr[-1000:])
        raise RuntimeError(f"Falha ao executar {' '.join(cmd)}")

    if result.stdout:
        logger.info("rel_veic_chao_sem_faturar stdout: %s", result.stdout[-1000:])

    return {"status": "ok", "command": " ".join(cmd)}
