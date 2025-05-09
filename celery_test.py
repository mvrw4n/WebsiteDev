#!/usr/bin/env python
"""
Script pour tester directement si Celery fonctionne correctement
"""
import os
import sys
import django
import logging
import traceback

# Configurer le logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Configurer l'environnement Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wizzydjango.settings.development')
django.setup()

def test_celery():
    """Test direct de Celery avec une tâche simple"""
    logger.info("=== TEST DIRECT DE CELERY ===")
    
    try:
        # Importer la tâche de test
        from scraping.tasks import verify_celery_connection
        
        # Exécuter la tâche de façon synchrone (local debug)
        logger.info("Exécution locale de verify_celery_connection")
        result_sync = verify_celery_connection.run(verify_celery_connection)
        logger.info(f"Résultat synchrone: {result_sync}")
        
        # Exécuter la tâche de façon asynchrone (via Celery)
        logger.info("Envoi asynchrone de la tâche verify_celery_connection à Celery")
        async_task = verify_celery_connection.delay()
        logger.info(f"Tâche envoyée avec ID: {async_task.id}")
        
        # Attendre le résultat avec timeout
        try:
            import time
            logger.info("Attente du résultat (max 5 secondes)...")
            for i in range(10):
                if async_task.ready():
                    result_async = async_task.get()
                    logger.info(f"Résultat asynchrone: {result_async}")
                    break
                time.sleep(0.5)
                logger.info(f"Attente... ({i+1}/10)")
            else:
                logger.warning("Timeout en attendant le résultat. La tâche n'a pas été traitée à temps.")
        except Exception as e:
            logger.error(f"Erreur en attendant le résultat: {str(e)}")
        
        # Tester une tâche simple qui ajoute des nombres
        from celery import shared_task
        
        @shared_task(name="test_add")
        def add(x, y):
            logger.info(f"Exécution de add({x}, {y})")
            return x + y
        
        logger.info("Envoi de la tâche add")
        add_task = add.delay(4, 5)
        logger.info(f"Tâche add envoyée avec ID: {add_task.id}")
        
        return True
    except Exception as e:
        logger.error(f"ERREUR: {str(e)}")
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_celery()
    
    if success:
        logger.info("✅ Test Celery terminé")
        sys.exit(0)
    else:
        logger.error("❌ Test Celery échoué")
        sys.exit(1) 