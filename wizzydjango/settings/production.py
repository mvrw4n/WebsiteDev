"""
Production settings for wizzydjango project.
"""

from .base import *
import os

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
# Database
# Database - Force using SQLite
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}
DEBUG = True

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,16.16.211.172,www.wizzy-lead.com').split(',')

# HTTPS settings
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# CORS settings - valeurs fixes sans dépendre des variables d'environnement
CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://16.16.211.172',
    'http://wizzy-lead.com',
    'http://www.wizzy-lead.com'
]
CORS_ALLOW_CREDENTIALS = True
# Static files
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'
# Configuration email pour Microsoft 365
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.office365.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'contact@wizard-lead.com'  # Votre adresse email
EMAIL_HOST_PASSWORD = 'Way-Psykozz22122000'  # Le mot de passe de votre compte email
DEFAULT_FROM_EMAIL = 'noreply@wizard-lead.com'


# Stripe settings
STRIPE_PUBLIC_KEY = os.environ.get('STRIPE_PUBLIC_KEY')
STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')

# Lifetime registration settings
LIFETIME_REGISTRATION_PASSWORD = os.environ.get('LIFETIME_REGISTRATION_PASSWORD')
if not LIFETIME_REGISTRATION_PASSWORD:
    raise ValueError('LIFETIME_REGISTRATION_PASSWORD environment variable must be set in production!')

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'django.log'),
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': os.environ.get('DJANGO_LOG_LEVEL', 'INFO'),
        },
        'billing': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
        },
    },
}

# Configuration Celery pour l'environnement de production
USE_CELERY = True  # Activer Celery en production

# En production, utilisez Redis via une variable d'environnement pour plus de sécurité
CELERY_BROKER_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

# Configuration pour la robustesse en production
CELERY_WORKER_CONCURRENCY = 4  # Nombre de processus workers
CELERY_WORKER_MAX_MEMORY_PER_CHILD = 200000  # 200MB
CELERY_BROKER_CONNECTION_MAX_RETRIES = None  # Réessayer indéfiniment
CELERY_BROKER_CONNECTION_TIMEOUT = 30  # Timeout de connexion en secondes

# Configuration de sécurité pour la production
CELERY_SECURITY_KEY = os.environ.get('CELERY_SECURITY_KEY', '')
CELERY_SECURITY_CERTIFICATE = os.environ.get('CELERY_SECURITY_CERTIFICATE', '')
CELERY_SECURITY_CERT_STORE = os.environ.get('CELERY_SECURITY_CERT_STORE', '') 
# Test de connexion à la base de données au démarrage
if not DEBUG:
    try:
        from django.db import connections
        db_conn = connections['default']
        c = db_conn.cursor()
        print("✅ Connexion à la base de données réussie")
    except Exception as e:
        print(f"❌ Erreur de connexion à la base de données: {e}")
# AI Models Configuration - copied from base settings to fix 'AIManager' missing mistral_config issue
AI_CONFIG = {
    'mistral': {
        'default_model': 'mistral-large-latest',
        'max_tokens': 8192,
        'temperature': 0.7,
        'rate_limit': {
            'requests_per_minute': 60,
            'min_delay_between_requests': 1.0  # seconds
        },
        'gdpr_compliance': {
            'enabled_by_default': True,  # Set to True to make GDPR compliance the default
            'configurable': True          # Allow users to toggle between modes
        }
    },
    'openai': {
        'default_model': 'gpt-4',
        'max_tokens': 1000,
        'temperature': 0.7,
        'rate_limit': {
            'requests_per_minute': 60,
            'min_delay_between_requests': 1.0  # seconds
        }
    }
} 
