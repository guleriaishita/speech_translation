from .settings import *
import os
import dj_database_url

# SECURITY
DEBUG = False
SECRET_KEY = os.environ.get('SECRET_KEY', 'CHANGE-THIS-IN-PRODUCTION')

# Allowed hosts
ALLOWED_HOSTS = [
    '.railway.app',
    '.vercel.app',
    'localhost',
    '127.0.0.1',
]

# CORS - Update with your frontend URL
CORS_ALLOWED_ORIGINS = [
    os.environ.get('FRONTEND_URL', 'http://localhost:3000'),
]

CORS_ALLOW_CREDENTIALS = True

# CSRF
CSRF_TRUSTED_ORIGINS = [
    'https://*.railway.app',
    'https://*.vercel.app',
]

# Database - Use Railway PostgreSQL or SQLite
if os.environ.get('DATABASE_URL'):
    DATABASES = {
        'default': dj_database_url.config(
            default=os.environ.get('DATABASE_URL'),
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    # Fallback to SQLite
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Static files
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATIC_URL = '/static/'

# Whitenoise for static files
MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Channels - Use Railway Redis
redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [redis_url],
        },
    },
}

# Celery - Use Railway Redis
CELERY_BROKER_URL = redis_url + '/1'
CELERY_RESULT_BACKEND = redis_url + '/2'

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}
