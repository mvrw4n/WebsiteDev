#!/usr/bin/env python
"""
Script pour inspecter l'état de Celery et des tâches en attente
"""
import os
import sys
import django
import logging
import traceback
import json
from datetime import datetime

# Configurer le logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Configurer l'environnement Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wizzydjango.settings.development')
django.setup()

def inspect_celery():
    """Inspecte l'état de Celery et des tâches en attente"""
    logger.info("=== INSPECTION CELERY ===")
    
    try:
        from celery.app.control import Inspect
        from celery import current_app
        
        # Créer un inspecteur
        inspect = Inspect(app=current_app)
        
        # Vérifier les nœuds actifs
        active_nodes = inspect.ping() or {}
        logger.info(f"Nœuds actifs: {list(active_nodes.keys())}")
        
        if not active_nodes:
            logger.error("❌ ERREUR: Aucun worker Celery actif")
            logger.info("Vérifiez que Celery est bien démarré avec 'python start_celery.py --with-beat'")
            return False
        
        # Stats
        stats = inspect.stats() or {}
        for worker, stat in stats.items():
            broker = stat.get('broker', {})
            logger.info(f"Worker: {worker}")
            logger.info(f"  Pool: {stat.get('pool', {}).get('max-concurrency', 'N/A')}")
            logger.info(f"  Broker: {broker.get('transport', 'N/A')} - {broker.get('hostname', 'N/A')}")
            logger.info(f"  Prefetch: {stat.get('prefetch_count', 'N/A')}")
        
        # Tâches enregistrées
        registered = inspect.registered() or {}
        logger.info("Tâches enregistrées:")
        for worker, tasks in registered.items():
            logger.info(f"  {worker}: {len(tasks)} tâches")
            scraping_tasks = [t for t in tasks if 'scraping' in t]
            logger.info(f"  Tâches de scraping: {scraping_tasks}")
        
        # Tâches actives
        active = inspect.active() or {}
        logger.info("Tâches actives:")
        for worker, tasks in active.items():
            logger.info(f"  {worker}: {len(tasks)} tâches")
            for task in tasks:
                logger.info(f"    {task['id']}: {task['name']} - args: {task['args']}")
        
        # Tâches réservées (en attente d'exécution)
        reserved = inspect.reserved() or {}
        logger.info("Tâches réservées:")
        for worker, tasks in reserved.items():
            logger.info(f"  {worker}: {len(tasks)} tâches")
            for task in tasks:
                logger.info(f"    {task['id']}: {task['name']} - args: {task['args']}")
        
        # Tâches planifiées
        scheduled = inspect.scheduled() or {}
        logger.info("Tâches planifiées:")
        for worker, tasks in scheduled.items():
            logger.info(f"  {worker}: {len(tasks)} tâches")
            for task in tasks:
                logger.info(f"    {task['id']}: {task['name']} - args: {task['args']}")
                
        # Vérifier le broker (Redis)
        try:
            import redis
            from django.conf import settings
            
            redis_url = settings.CELERY_BROKER_URL
            logger.info(f"Connexion à Redis: {redis_url}")
            
            r = redis.Redis.from_url(redis_url)
            redis_info = r.info()
            logger.info(f"Redis version: {redis_info.get('redis_version', 'N/A')}")
            logger.info(f"Mémoire utilisée: {redis_info.get('used_memory_human', 'N/A')}")
            
            # Lister les clés Celery
            celery_keys = r.keys('celery*')
            logger.info(f"Clés Celery dans Redis: {len(celery_keys)}")
            for key in celery_keys[:10]:  # Limiter à 10 clés
                logger.info(f"  {key.decode('utf-8')}")
            
        except Exception as redis_e:
            logger.error(f"Erreur lors de la connexion à Redis: {str(redis_e)}")
        
        # Vérifier les tâches en base de données
        from scraping.models import ScrapingTask
        
        pending_tasks = ScrapingTask.objects.filter(status='pending').count()
        initializing_tasks = ScrapingTask.objects.filter(status='initializing').count()
        running_tasks = ScrapingTask.objects.filter(status__in=['crawling', 'extracting', 'processing']).count()
        failed_tasks = ScrapingTask.objects.filter(status='failed').count()
        
        logger.info("Tâches en base de données:")
        logger.info(f"  Pending: {pending_tasks}")
        logger.info(f"  Initializing: {initializing_tasks}")
        logger.info(f"  Running: {running_tasks}")
        logger.info(f"  Failed: {failed_tasks}")
        
        # Afficher les tâches en initialisation pour diagnostic
        init_tasks = ScrapingTask.objects.filter(status='initializing').order_by('-id')[:5]
        if init_tasks:
            logger.info("Tâches en initialisation:")
            for task in init_tasks:
                logger.info(f"  ID: {task.id}, Job: {task.job.name}")
                logger.info(f"  Celery task ID: {task.celery_task_id}")
                logger.info(f"  Current step: {task.current_step}")
                logger.info(f"  Start time: {task.start_time}")
        
        # Récupérer les logs d'erreur récents
        from scraping.models import ScrapingLog
        
        error_logs = ScrapingLog.objects.filter(log_type='error').order_by('-timestamp')[:5]
        if error_logs:
            logger.info("Erreurs récentes:")
            for log in error_logs:
                logger.info(f"  {log.timestamp}: {log.message}")
        
        return True
        
    except Exception as e:
        logger.error(f"ERREUR lors de l'inspection Celery: {str(e)}")
        logger.error(traceback.format_exc())
        return False

def purge_tasks():
    """Purger toutes les tâches en attente dans la file Celery"""
    try:
        from celery import current_app
        
        logger.info("Purge de la file d'attente Celery...")
        result = current_app.control.purge()
        logger.info(f"Tâches purgées: {result}")
        return True
    except Exception as e:
        logger.error(f"Erreur lors de la purge: {str(e)}")
        return False

def reset_initializing_tasks():
    """Réinitialiser toutes les tâches bloquées en statut 'initializing'"""
    try:
        from scraping.models import ScrapingTask
        from django.utils import timezone
        
        # Trouver les tâches bloquées (statut 'initializing' depuis plus de 10 minutes)
        stuck_time = timezone.now() - timezone.timedelta(minutes=10)
        stuck_tasks = ScrapingTask.objects.filter(
            status='initializing',
            start_time__lt=stuck_time
        )
        
        count = stuck_tasks.count()
        if count > 0:
            logger.info(f"Réinitialisation de {count} tâches bloquées en 'initializing'...")
            
            for task in stuck_tasks:
                logger.info(f"  Réinitialisation de la tâche {task.id} (Job: {task.job.name})")
                task.status = 'pending'
                task.current_step = 'Tâche en file d\'attente...'
                task.save()
            
            logger.info(f"{count} tâches réinitialisées")
        else:
            logger.info("Aucune tâche bloquée en 'initializing'")
        
        return True
    except Exception as e:
        logger.error(f"Erreur lors de la réinitialisation des tâches: {str(e)}")
        return False

def force_run_task(task_id):
    """Forcer l'exécution directe d'une tâche spécifique"""
    logger.info(f"=== EXÉCUTION FORCÉE DE LA TÂCHE {task_id} ===")
    
    try:
        from scraping.models import ScrapingTask, ScrapingLog, ScrapingResult, ScrapedSite
        from core.models import Lead
        import socket
        import random
        import time
        from bs4 import BeautifulSoup
        from urllib.parse import urlparse
        from django.utils import timezone
        
        # Récupérer la tâche
        task = ScrapingTask.objects.get(id=task_id)
        logger.info(f"Tâche trouvée: {task}")
        logger.info(f"  Job: {task.job.name}")
        logger.info(f"  Status: {task.status}")
        
        # Mettre à jour le statut
        task.status = 'crawling'
        task.current_step = "Exploration forcée des sites web..."
        task.save()
        
        # Log de l'exécution forcée
        ScrapingLog.objects.create(
            task=task,
            log_type='info',
            message=f"FORCE: Exécution forcée de la tâche sur {socket.gethostname()}",
            details={
                "worker": socket.gethostname(),
                "mode": "FORCE_DIRECT"
            }
        )
        
        # Récupérer le job et la structure
        job = task.job
        structure = job.structure
        
        # Simuler un scraping simple avec création de leads
        for i in range(3):
            logger.info(f"Génération du lead {i+1}/3...")
            
            # Simuler un lead
            lead_data = {
                "nom": f"Contact Test {i+1}",
                "fonction": "Responsable Test",
                "email": f"test{i+1}@example.com",
                "telephone": f"+33 6 12 34 56 {78+i}",
                "source": "Test direct",
                "domaine": "example.com"
            }
            
            # Créer un résultat de scraping
            scraping_result = ScrapingResult.objects.create(
                task=task,
                lead_data=lead_data,
                source_url="https://example.com/test",
                is_duplicate=False
            )
            
            # Créer un lead
            lead = Lead.objects.create(
                scraping_result=scraping_result,
                user=job.user,
                name=lead_data["nom"],
                email=lead_data["email"],
                phone=lead_data["telephone"],
                company="Example Company",
                position=lead_data["fonction"],
                status='not_contacted',
                source="Test direct",
                source_url="https://example.com/test",
                data=lead_data
            )
            
            # Incrémenter les compteurs
            task.pages_explored += 1
            task.leads_found += 1
            task.unique_leads += 1
            task.save()
            
            # Log du lead
            ScrapingLog.objects.create(
                task=task,
                log_type='success',
                message=f"FORCE: Lead créé: {lead_data['nom']}",
                details={"lead": lead_data, "lead_id": lead.id}
            )
            
            # Mise à jour du quota utilisateur
            profile = job.user.profile
            if not profile.unlimited_leads:
                profile.leads_used += 1
                profile.save()
            
            # Pause
            time.sleep(1)
        
        # Terminer la tâche
        task.status = 'completed'
        task.current_step = "Tâche forcée terminée avec succès"
        task.completion_time = timezone.now()
        task.save()
        
        # Mettre à jour le job
        job.leads_found = task.unique_leads
        job.status = 'completed'
        job.save()
        
        # Log final
        ScrapingLog.objects.create(
            task=task,
            log_type='success',
            message=f"FORCE: Tâche forcée terminée avec succès - {task.unique_leads} leads générés",
            details={
                "total_leads": task.leads_found,
                "unique_leads": task.unique_leads,
                "pages_explored": task.pages_explored,
                "mode": "FORCE_DIRECT"
            }
        )
        
        logger.info(f"Tâche {task_id} forcée terminée avec succès")
        return True
        
    except Exception as e:
        logger.error(f"ERREUR: {str(e)}")
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python celery_debugger.py [inspect|purge|reset|force_run <task_id>]")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "inspect":
        success = inspect_celery()
    elif command == "purge":
        success = purge_tasks()
    elif command == "reset":
        success = reset_initializing_tasks()
    elif command == "force_run" and len(sys.argv) > 2:
        task_id = int(sys.argv[2])
        success = force_run_task(task_id)
    else:
        print(f"Commande inconnue: {command}")
        print("Usage: python celery_debugger.py [inspect|purge|reset|force_run <task_id>]")
        sys.exit(1)
    
    if success:
        logger.info("✅ Opération terminée avec succès")
        sys.exit(0)
    else:
        logger.error("❌ Opération échouée")
        sys.exit(1) 