"""
Base settings for wizzydjango project.
Contains all common settings used in both development and production.
"""

from pathlib import Path
import os
from datetime import timedelta
from django.core.management.utils import get_random_secret_key

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', get_random_secret_key())

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []

# Application definition
INSTALLED_APPS = [
    # Django core
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third party
    'rest_framework',
    'rest_framework_simplejwt',
    'djoser',
    'corsheaders',
    'widget_tweaks',

    # Local
    'core',
    'billing',
    'scraping',
    'django_celery_results',
    'django_celery_beat',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'wizzydjango.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'templates'),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'wizzydjango.wsgi.application'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Database
# This is a default configuration that will be overridden by development or production settings
# It's here to ensure Celery can start properly using the base settings
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom user model
AUTH_USER_MODEL = 'core.CustomUser'

# REST Framework settings
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
}

# JWT settings
SIMPLE_JWT = {
    'AUTH_HEADER_TYPES': ('Bearer',),
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),  # Increase from default 5 minutes
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),     # Increase from default 1 day
    'ROTATE_REFRESH_TOKENS': True,                   # Get new refresh token when refreshing access token
    'BLACKLIST_AFTER_ROTATION': True,               # Blacklist old refresh tokens
    'UPDATE_LAST_LOGIN': True,                      # Update last login timestamp
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'USER_AUTHENTICATION_RULE': 'rest_framework_simplejwt.authentication.default_user_authentication_rule',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'TOKEN_TYPE_CLAIM': 'token_type',
    'JTI_CLAIM': 'jti',
    'TOKEN_USER_CLASS': 'rest_framework_simplejwt.models.TokenUser',
}

# Djoser settings
DJOSER = {
    'LOGIN_FIELD': 'email',
    'USER_CREATE_PASSWORD_RETYPE': True,
    'USERNAME_CHANGED_EMAIL_CONFIRMATION': True,
    'PASSWORD_CHANGED_EMAIL_CONFIRMATION': True,
    'SEND_CONFIRMATION_EMAIL': True,
    'PASSWORD_RESET_CONFIRM_URL': 'password/reset/confirm/{uid}/{token}',
    'USERNAME_RESET_CONFIRM_URL': 'email/reset/confirm/{uid}/{token}',
    'ACTIVATION_URL': 'activate/{uid}/{token}',
    'SEND_ACTIVATION_EMAIL': True,
    'SERIALIZERS': {
        'user_create': 'core.serializers.CustomUserCreateSerializer',
        'user': 'core.serializers.CustomUserSerializer',
        'current_user': 'core.serializers.CustomUserSerializer',
    },
    'EMAIL': {
        'activation': 'core.email.ActivationEmail',
        'confirmation': 'core.email.ConfirmationEmail',
        'password_reset': 'core.email.PasswordResetEmail',
        'password_changed_confirmation': 'core.email.PasswordChangedConfirmationEmail',
    },
    'TOKEN_MODEL': None,  # We're using JWT tokens
    'HIDE_USERS': True,  # Hide users list from non-admin users
    'PERMISSIONS': {
        'user': ['rest_framework.permissions.IsAuthenticated'],
        'user_list': ['rest_framework.permissions.IsAdminUser'],
    }
}

# Email settings
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'  # Update with your SMTP server
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')  # Set in environment variables
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')  # Set in environment variables

# CORS settings
CORS_ALLOW_CREDENTIALS = True

# Stripe settings
STRIPE_PUBLIC_KEY = os.environ.get('STRIPE_PUBLIC_KEY', '')
STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')

# Lifetime registration settings
LIFETIME_REGISTRATION_PASSWORD = "Wizzy2025SecuredPasswordyes!"

# AI and API Keys Settings
OPENAI_API_KEY = "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"
SERPER_API_KEY = "5f46e4b1ac09caa43c3be2941fc21891d10316c6"
MISTRAL_API_KEY = "jjOWwJTSrXepsu0vg06O6nxN5QyYmaKE"
DROPCONTACT_API_KEY = os.getenv('DROPCONTACT_API_KEY', '')

# AI Models Configuration
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

# Scraping Configuration
SCRAPING_CONFIG = {
    'serp': {
        'results_per_page': 10,
        'max_pages': 4,
        'rate_limit': {
            'requests_per_minute': 60,
            'min_delay_between_requests': 1.0  # seconds
        }
    },
    'linkedin': {
        'max_profiles_per_search': 100,
        'rate_limit': {
            'requests_per_minute': 30,
            'min_delay_between_requests': 2.0  # seconds
        }
    },
    'dropcontact': {
        'batch_size': 50,
        'rate_limit': {
            'requests_per_minute': 100,
            'min_delay_between_requests': 0.6  # seconds
        }
    }
}

# Scraping Scenarios Templates
SCRAPING_TEMPLATES = {
    'mairie': {
        'structure': {
            'mairie': {
                'nom': '',
                'code_postal': '',
                'site_web': '',
                'adresse': '',
                'description': '',
                'infrastructure_sportive': {
                    'gazon_naturel': 0,
                    'gazon_synthetique': 0
                },
                'meta_data': {
                    'priority_links': []
                }
            },
            'contacts': [
                {
                    'nom': '',
                    'email': '',
                    'telephone': '',
                    'fonction': '',
                    'Profile linkedin': ''
                }
            ],
            'tenders': [
                {
                    'titre': '',
                    'description': '',
                    'lien': '',
                    'budget': '',
                    'date/durée': ''
                }
            ]
        }
    },
    'b2b_company': {
        'structure': {
            'company': {
                'name': '',
                'website': '',
                'industry': '',
                'size': '',
                'revenue': '',
                'description': '',
                'social_media': {
                    'linkedin': '',
                    'twitter': ''
                }
            },
            'contacts': [
                {
                    'name': '',
                    'title': '',
                    'email': '',
                    'phone': '',
                    'linkedin': ''
                }
            ],
            'meta_data': {
                'source': '',
                'last_updated': '',
                'confidence_score': 0
            }
        }
    }
}

# AI Action Types
AI_ACTION_TYPES = [
    ('serp_scraping', 'SERP Scraping'),
    ('linkedin_scraping', 'LinkedIn Scraping'),
    ('dropcontact_enrichment', 'Dropcontact Enrichment'),
    ('custom_scraping', 'Custom Scraping'),
]

# Scraping Strategies
SCRAPING_STRATEGIES = {
    'web_scraping': {
        'name': 'Web Scraping',
        'description': {
            'fr': "Cette stratégie explore différents sites web pour collecter les données. Elle analyse les pages pertinentes, identifie et extrait les informations correspondant à la structure définie, en utilisant des techniques d'extraction avancées.",
            'en': "This strategy explores various websites to collect data. It analyzes relevant pages, identifies and extracts information matching the defined structure, using advanced extraction techniques."
        }
    },
    'linkedin_scraping': {
        'name': 'LinkedIn Scraping',
        'description': {
            'fr': "Cette stratégie se concentre sur l'extraction de données professionnelles depuis LinkedIn. Elle cible les profils d'entreprises et d'individus correspondant aux critères définis, en récupérant les informations de contact et détails professionnels.",
            'en': "This strategy focuses on extracting professional data from LinkedIn. It targets company and individual profiles matching the defined criteria, retrieving contact information and professional details."
        }
    },
    'custom_scraping': {
        'name': 'Scraping Personnalisé',
        'description': {
            'fr': "Cette stratégie personnalisée adapte les techniques d'extraction aux besoins spécifiques de la structure. Elle combine différentes approches pour maximiser la pertinence et la qualité des données collectées.",
            'en': "This custom strategy adapts extraction techniques to the specific needs of the structure. It combines different approaches to maximize the relevance and quality of the collected data."
        }
    },
    'api_scraping': {
        'name': 'API Scraping',
        'description': {
            'fr': "Cette stratégie utilise des APIs et sources de données structurées pour collecter les informations. Elle permet d'obtenir des données précises et à jour directement depuis les services qui les proposent.",
            'en': "This strategy uses APIs and structured data sources to collect information. It allows obtaining accurate and up-to-date data directly from the services that offer them."
        }
    }
}

# Language Settings
LANGUAGE_SETTINGS = {
    'default': 'fr',
    'available': ['fr', 'en'],
    'responses': {
        'fr': {
            'error': 'Je suis désolé, une erreur est survenue. Veuillez réessayer.',
            'welcome': 'Bonjour! Je suis votre assistant IA. Comment puis-je vous aider?',
            'processing': 'Je traite votre demande...',
            'success': 'Voici les résultats de votre recherche:',
            'no_results': 'Désolé, je n\'ai pas trouvé de résultats pour votre recherche.',
            'clarification': 'Pourriez-vous préciser votre demande?',
            'default_response': 'Je comprends votre demande. Comment puis-je vous aider davantage?'
        },
        'en': {
            'error': 'I apologize, an error occurred. Please try again.',
            'welcome': 'Hello! I am your AI assistant. How can I help you?',
            'processing': 'Processing your request...',
            'success': 'Here are the results of your search:',
            'no_results': 'Sorry, I couldn\'t find any results for your search.',
            'clarification': 'Could you please clarify your request?',
            'default_response': 'I understand your request. How can I help you further?'
        }
    }
}

# AI Response Templates
AI_RESPONSE_TEMPLATES = {
    'serp_scraping': {
        'fr': {
            'start': 'Je vais effectuer une recherche sur le web pour trouver {query}.',
            'processing': 'Analyse des résultats en cours...',
            'success': 'J\'ai trouvé {count} résultats pertinents.',
            'error': 'Désolé, je n\'ai pas pu effectuer la recherche.'
        },
        'en': {
            'start': 'I will search the web to find {query}.',
            'processing': 'Analyzing results...',
            'success': 'I found {count} relevant results.',
            'error': 'Sorry, I couldn\'t perform the search.'
        }
    },
    'linkedin_scraping': {
        'fr': {
            'start': 'Je vais chercher des profils LinkedIn correspondant à vos critères.',
            'processing': 'Analyse des profils en cours...',
            'success': 'J\'ai trouvé {count} profils correspondants.',
            'error': 'Désolé, je n\'ai pas pu accéder aux profils LinkedIn.'
        },
        'en': {
            'start': 'I will search for LinkedIn profiles matching your criteria.',
            'processing': 'Analyzing profiles...',
            'success': 'I found {count} matching profiles.',
            'error': 'Sorry, I couldn\'t access the LinkedIn profiles.'
        }
    }
}

# Configuration Celery
# Paramètres de base pour Celery
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'

# Format des tâches de Celery (json pour une meilleure compatibilité)
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'

# Paramètres de timezone pour Celery
CELERY_TIMEZONE = TIME_ZONE

# Configuration des files d'attente Celery pour prioriser certaines tâches
CELERY_TASK_ROUTES = {
    'scraping.tasks.verify_celery_connection': {'queue': 'celery'},  # File par défaut
    'scraping.tasks.run_scraping_task': {'queue': 'scraping'},
    'scraping.tasks.start_structure_scrape': {'queue': 'scraping'},
    'scraping.tasks.test_celery_connection': {'queue': 'celery'},  # File par défaut
}

# Définir les files d'attente que le worker doit traiter
CELERY_QUEUES = {
    'celery': {'exchange': 'celery', 'routing_key': 'celery'},
    'scraping': {'exchange': 'scraping', 'routing_key': 'scraping'},
    'check': {'exchange': 'check', 'routing_key': 'check'},
}

# Par défaut, activer Celery en production
USE_CELERY = True

# Configuration additionnelle
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 3600  # 1 heure
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BROKER_TRANSPORT_OPTIONS = {'visibility_timeout': 43200}  # 12 heures

# Configuration pour le timeout des résultats (évite les timeouts comme celui que vous avez eu)
CELERY_RESULT_EXPIRES = 3600  # 1 heure
CELERY_TASK_RESULT_EXPIRES = 3600  # 1 heure

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': 'logs/django.log',
            'formatter': 'verbose',
        },
        'scraping_file': {
            'class': 'logging.FileHandler',
            'filename': 'logs/scraping.log',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
        'scraping': {
            'handlers': ['console', 'scraping_file'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'celery': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
} 