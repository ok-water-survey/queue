#Cybercommons Parameter set
#BROKER_URL = 'amqp://jduckles:cybercommons@fire.rccc.ou.edu:5672/cybercom_test'
#CELERY_RESULT_BACKEND = "mongodb"
#CELERY_MONGODB_BACKEND_SETTINGS = {
#    "host": "localhost",
#    "database": "cybercom_queue",
#    "taskmeta_collection": "cybercom_queue_meta"
#}

#Oklahoma Water Survey Parameter set
#BROKER_URL = 'amqp://mstacy:welcome1@fire.rccc.ou.edu:5672/okwater'
BROKER_URL = 'amqp://mstacy:owspass@129.15.41.96:5672/okwater'
CELERY_RESULT_BACKEND = "mongodb"
CELERY_MONGODB_BACKEND_SETTINGS = {
    "host": "worker.oklahomawatersurvey.org",#"localhost",
    "database": "cybercom_queue",
    "taskmeta_collection": "okwater"
}
