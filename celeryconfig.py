#Oklahoma Water Survey Parameter set
from config import CELERY_BROKER

BROKER_URL = CELERY_BROKER
CELERY_RESULT_BACKEND = "mongodb"
CELERY_MONGODB_BACKEND_SETTINGS = {
    "host": "worker.oklahomawatersurvey.org",
    "database": "cybercom_queue",
    "taskmeta_collection": "okwater"
}
