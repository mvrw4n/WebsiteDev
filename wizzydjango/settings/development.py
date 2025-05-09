"""
Development settings for wizzydjango project.
"""

from .base import *

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-lp_dyw2f$a79t9$ioe-4yfwew#y!t5ejzxkf&%4w3e3_45q*_8'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# CORS settings for development
CORS_ALLOW_ALL_ORIGINS = True

# Debug toolbar settings
INSTALLED_APPS += ['debug_toolbar']
MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']
INTERNAL_IPS = ['127.0.0.1']

# Email settings for development
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Stripe test keys
STRIPE_PUBLIC_KEY = 'pk_test_51R6fGIFbWog8HEBlvohdOkLhihoiNtmJyvHtbg8WnMq2eHxLubNUij4gZx2vQsKeP4w1Gxz8PEFrBWNAbX66DJbB00c3OsK3XU'
STRIPE_SECRET_KEY = 'sk_test_your_stripe_secret_key'
STRIPE_WEBHOOK_SECRET = 'whsec_your_stripe_webhook_secret'

# Override the lifetime registration password for development
LIFETIME_REGISTRATION_PASSWORD = 'wizzy2025_dev_only'  # This is only for development!

# Personnalisation de Celery pour l'environnement de développement
USE_CELERY = True  # Activer Celery en développement

# En développement, utilisez une configuration Redis locale
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'

# Activer plus de logs pour le développement
CELERY_WORKER_HIJACK_ROOT_LOGGER = False  # Ne pas détourner le logger racine
CELERY_WORKER_LOG_FORMAT = '%(asctime)s [%(levelname)s] %(message)s' 