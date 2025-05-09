#!/usr/bin/env python
"""
Script de test pour vérifier que Celery fonctionne correctement
"""
import os
import sys
import django
import time

# Configurer l'environnement Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wizzydjango.settings.development')
django.setup()

from django.conf import settings
import logging

# Configurer le logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def test_celery_connection():
    """Teste la connexion Celery en lançant une tâche simple"""
    try:
        logger.info("Test de la connexion Celery...")
        
        # Vérifier si Celery est activé
        if not hasattr(settings, 'USE_CELERY') or not settings.USE_CELERY:
            logger.error("Celery n'est pas activé dans les paramètres Django (USE_CELERY=False)")
            return False
        
        # Vérifier la configuration Celery
        logger.info(f"URL du broker: {settings.CELERY_BROKER_URL}")
        logger.info(f"URL du backend: {settings.CELERY_RESULT_BACKEND}")
        
        # Tester connexion Redis
        try:
            import redis
            r = redis.from_url(settings.CELERY_BROKER_URL)
            r.ping()
            logger.info("Connexion Redis OK")
        except Exception as e:
            logger.error(f"Erreur de connexion Redis: {str(e)}")
            return False
        
        # Importer et tester une tâche simple
        try:
            from scraping.tasks import test_celery_connection
            logger.info("Exécution d'une tâche de test...")
            result = test_celery_connection.delay()
            
            # Attendre le résultat
            logger.info("Attente du résultat...")
            for i in range(10):  # 10 secondes max
                if result.ready():
                    res = result.get()
                    logger.info(f"Résultat reçu: {res}")
                    return True
                time.sleep(1)
                logger.info(f"Attente... {i+1}s")
            
            logger.error("Délai d'attente dépassé - Les workers Celery sont-ils en cours d'exécution?")
            return False
            
        except Exception as e:
            logger.error(f"Erreur lors de l'exécution de la tâche: {str(e)}")
            return False
            
    except Exception as e:
        logger.error(f"Erreur lors du test Celery: {str(e)}")
        return False

if __name__ == "__main__":
    logger.info("=== TEST CELERY ===")
    success = test_celery_connection()
    if success:
        logger.info("✅ Test réussi! Celery fonctionne correctement.")
        sys.exit(0)
    else:
        logger.error("❌ Échec du test. Celery ne fonctionne pas correctement.")
        logger.info("\nConseil: Assurez-vous que le worker Celery est en cours d'exécution avec:")
        logger.info("  python start_celery.py")
        sys.exit(1) 