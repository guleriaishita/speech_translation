web: daphne -b 0.0.0.0 -p $PORT speech_translator.asgi:application
worker: celery -A speech_translator worker -l info --concurrency=2
