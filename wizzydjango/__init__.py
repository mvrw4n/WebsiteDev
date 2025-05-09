# Configuration de Celery
from __future__ import absolute_import, unicode_literals

# Ce code garantit que l'application Celery est chargée au démarrage de Django
# Utilisation d'une fonction pour éviter les importations circulaires
def _get_celery_app():
    from .celery import app as celery_app
    return celery_app

# Définir la variable dans un try-except pour gérer les erreurs potentielles d'importation
try:
    celery_app = _get_celery_app()
    __all__ = ('celery_app',)
except Exception as e:
    # En cas d'erreur, on continue quand même pour que Django puisse démarrer
    import logging
    logging.getLogger(__name__).warning(f"Erreur lors de l'initialisation de Celery: {e}")
    __all__ = ()
