import os
from celery import Celery
import logging
import signal
import sys

logger = logging.getLogger(__name__)

# Obtenir l'environnement depuis les variables d'environnement (development par défaut)
environment = os.environ.get('DJANGO_ENV', 'development')

# Configuration Django
if environment == 'production':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wizzydjango.settings.production')
    logger.info("Celery démarre avec les paramètres de PRODUCTION")
else:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wizzydjango.settings.development')
    logger.info("Celery démarre avec les paramètres de DÉVELOPPEMENT")

# Création de l'application Celery
app = Celery('wizzydjango')

# Utilisation des paramètres de config depuis le fichier settings.py
app.config_from_object('django.conf:settings', namespace='CELERY')

# Découverte automatique des tâches dans les apps Django
app.autodiscover_tasks()

# Importer ici explicitement les tâches périodiques pour éviter les erreurs
# "Task not registered"
import scraping.tasks

# Définir les tâches périodiques dans beat_schedule
# Mais sans utiliser les références directes aux fonctions qui pourraient ne pas être
# encore importées/enregistrées
app.conf.beat_schedule = {
    'check-user-agents': {
        'task': 'scraping.tasks.check_user_agents',
        'schedule': 300.0,  # Run every 5 minutes
        'options': {'expires': 290},
    },
    'cleanup-old-tasks': {
        'task': 'scraping.tasks.cleanup_old_tasks',
        'schedule': 86400.0,  # Run once per day
        'options': {'expires': 86000},
    },
    'verify-celery-connection': {
        'task': 'scraping.tasks.verify_celery_connection',
        'schedule': 3600.0,  # Run every hour
        'options': {'expires': 3500},
    },
    'check-pending-tasks': {
        'task': 'scraping.tasks.check_pending_tasks',
        'schedule': 60.0,  # Run every minute
        'options': {'expires': 55},
    }
}

@app.task(bind=True)
def debug_task(self):
    """Tâche simple pour tester la configuration Celery"""
    logger.info(f"Celery debug task (ID: {self.request.id}) exécutée avec succès")
    return {"status": "success", "message": "Celery est correctement configuré"}

# Signal handling for proper shutdown
def on_worker_shutdown(signal, frame):
    """Handle clean shutdown of workers"""
    logger.info("SHUTDOWN: Received signal to terminate workers")
    
    # Kill worker immediately - don't wait for tasks to complete
    logger.info("SHUTDOWN: Force terminating all worker processes")
    os._exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, on_worker_shutdown)
signal.signal(signal.SIGTERM, on_worker_shutdown)

# Additional Celery configuration
app.conf.update(
    worker_max_tasks_per_child=1000,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    broker_transport_options={'visibility_timeout': 43200},  # 12 hours
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour,
    worker_cancel_long_running_tasks_on_connection_loss=True,  # Cancel tasks on connection loss
    worker_shutdown_timeout=10,  # Don't wait too long for tasks to finish on shutdown
) 