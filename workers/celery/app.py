from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv
import os

load_dotenv()

BROKER_URL = os.getenv("CELERY_BROKER_URL", "pyamqp://guest:guest@rabbitmq:5672//")

app = Celery(
    "tasks",
    broker=BROKER_URL,
    backend="rpc://",
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Sao_Paulo",
    enable_utc=True,
    task_track_started=True,
    result_expires=3600,
    beat_schedule={
        "fix-connections-nbs-every-60s": {
            "task": "tasks.fix_connections.fix_connections_nbs",
            "schedule": 60.0,
        },
        "send-acompanhamento-diretoria-13-00": {
            "task": "tasks.acompanhamento_diretoria.send_acompanhamento_diretoria",
            "schedule": crontab(hour=13, minute=0, day_of_week='1-5'),
        },
        "send-acompanhamento-diretoria-17-30": {
            "task": "tasks.acompanhamento_diretoria.send_acompanhamento_diretoria",
            "schedule": crontab(hour=17, minute=30, day_of_week='1-5'),
        },
        "send-acompanhamento-diretoria-18-00": {
            "task": "tasks.acompanhamento_diretoria.send_acompanhamento_diretoria",
            "schedule": crontab(hour=18, minute=0, day_of_week='1-5'),
        },
        "fix-crm-proposta-zero-every-5min": {
            "task": "tasks.fix_crm_proposta.fix_crm_proposta_zero",
            "schedule": 300.0,
        },
        "sync-propostas-rdstation-every-30s": {
            "task": "tasks.sync_rdstation.sync_propostas_rdstation",
            "schedule": 30.0,
        },
    },
)

app.conf.imports = ["tasks.fix_connections", "tasks.acompanhamento_diretoria", "tasks.fix_crm_proposta", "tasks.sync_rdstation"]

@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")

if __name__ == "__main__":
    app.start()
