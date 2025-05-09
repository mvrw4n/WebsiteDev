from celery import shared_task, Task
from django.utils import timezone
from django.db.models import Q
from django.conf import settings
import logging
from datetime import timedelta, datetime
import time
import socket
import json
import traceback
import os
import re
import requests
import asyncio
from celery.signals import task_prerun, task_postrun, task_success, task_failure
from functools import wraps
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# Configuration détaillée du logging
logger = logging.getLogger('scraping')  # Utiliser le logger 'scraping' configuré dans settings
logger.setLevel(logging.DEBUG)

# Ajouter un handler pour la console si ce n'est pas déjà fait
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

# Ajouter un handler pour un fichier de log spécifique aux tâches
file_handler = logging.FileHandler('logs/scraping_tasks.log')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Log initial pour confirmer la configuration
logger.info("=== Configuration du logging terminée pour scraping.tasks ===")
logger.info(f"Niveau de log actuel: {logger.getEffectiveLevel()}")
logger.info(f"Handlers configurés: {[h.__class__.__name__ for h in logger.handlers]}")

# Déplacer les importations de modèles à l'intérieur des fonctions
# pour éviter les importations circulaires
# from core.models import ScrapingJob, ScrapingStructure, CustomUser, Lead
# from .models import ScrapingTask, ScrapingLog, ScrapingResult, TaskQueue, ScrapedSite

# Signaux Celery pour le débogage  
@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **extras):
    """Log when task begins execution"""
    logger.debug(f"PRERUN: Task {task.name}[{task_id}] started with args={args}, kwargs={kwargs}")

@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, retval=None, state=None, **extras):
    """Log when task completes execution"""
    logger.debug(f"POSTRUN: Task {task.name}[{task_id}] ended with state={state}")

@task_success.connect
def task_success_handler(sender=None, result=None, **kwargs):
    """Log when task succeeds"""
    logger.debug(f"SUCCESS: Task {sender.name} succeeded with result={result}")

@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, args=None, kwargs=None, traceback=None, einfo=None, **extras):
    """Log when task fails"""
    logger.error(f"FAILURE: Task {sender.name}[{task_id}] failed with exception={exception}")
    logger.error(f"FAILURE: Traceback: {einfo}")

# Global flag to control automatic scraping
AUTOMATIC_SCRAPING_ENABLED = True
USING_SIMULATION = False  # Forcer le mode PRODUCTION avec Celery

# Fonction simplifiée juste pour le logging, la simulation est désactivée de force
def check_celery_status():
    """
    Vérifie si Celery est disponible et configuré.
    Retourne un tuple (is_available, message)
    """
    try:
        try:
            from celery.app.control import Inspect
            from celery import current_app
            import redis
            
            # Vérifier d'abord la connexion Redis
            redis_client = redis.Redis.from_url(settings.CELERY_BROKER_URL)
            redis_client.ping()
            
            # Vérifier les workers Celery
            inspect = Inspect(app=current_app)
            stats = inspect.stats()
            
            if not stats:
                logger.warning("Aucun worker Celery actif, mais nous forçons quand même le mode PRODUCTION.")
                return True, "Mode PRODUCTION forcé (workers non détectés)"
            
            worker_count = len(stats)
            worker_names = list(stats.keys())
            
            msg = f"Celery disponible avec {worker_count} worker(s): {', '.join(worker_names)}"
            logger.info(msg)
            return True, msg
            
        except Exception as e:
            logger.warning(f"Problème avec Celery/Redis, mais nous forçons quand même le mode PRODUCTION: {str(e)}")
            return True, "Mode PRODUCTION forcé (erreur connection)"
            
    except Exception as e:
        logger.error(f"Erreur lors de la vérification Celery: {str(e)}")
        return True, "Mode PRODUCTION forcé (erreur inconnue)"

# Force le mode production pour tous les cas
logger.info("Mode PRODUCTION avec Celery activé (simulation désactivée).")

# Base class for tasks with enhanced logging
class LoggingTask(Task):
    """Base Task class for better logging"""
    
    def on_success(self, retval, task_id, args, kwargs):
        logger.info(f"Task {self.name}[{task_id}] completed successfully")
        return super().on_success(retval, task_id, args, kwargs)
        
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(f"Task {self.name}[{task_id}] failed: {str(exc)}")
        return super().on_failure(exc, task_id, args, kwargs, einfo)
        
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        logger.warning(f"Task {self.name}[{task_id}] retrying: {str(exc)}")
        return super().on_retry(exc, task_id, args, kwargs, einfo)

# Worker activity tracking utility functions
def update_worker_activity(task_id, activity_type, status, current_url=None, details=None):
    """Update the worker activity for a task"""
    try:
        # Importations à l'intérieur de la fonction pour éviter les importations circulaires
        from .models import CeleryWorkerActivity, ScrapingTask
        
        # Try to find the ScrapingTask with this celery task ID
        task = ScrapingTask.objects.filter(celery_task_id=task_id).first()
        
        # Get or create worker activity
        worker_name = f"worker-{socket.gethostname()}"
        
        activity, created = CeleryWorkerActivity.objects.update_or_create(
            worker_name=worker_name,
            hostname=socket.gethostname(),
            defaults={
                'task': task,
                'activity_type': activity_type,
                'status': status,
                'current_url': current_url,
                'details': details or {}
            }
        )
        
        logger.debug(f"Updated worker activity: {activity}")
        return activity
    except Exception as e:
        logger.error(f"Error updating worker activity: {str(e)}")
        return None

# Decorator for tracking task activity
def track_scraping_activity(activity_type):
    """Decorator to track scraping activity for a task"""
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # Update activity to running at start
            update_worker_activity(
                self.request.id, 
                activity_type, 
                'running',
                details={'args': args, 'kwargs': kwargs}
            )
            
            try:
                # If first arg is a task_id, let's update the ScrapingTask with the celery task ID
                if args and isinstance(args[0], (int, str)):
                    from scraping.models import ScrapingTask
                    try:
                        task_id = int(args[0])
                        task = ScrapingTask.objects.filter(id=task_id).first()
                        if task:
                            task.celery_task_id = self.request.id
                            task.save(update_fields=['celery_task_id'])
                    except (ValueError, TypeError):
                        pass
                
                # Run the original task
                result = func(self, *args, **kwargs)
                
                # Update activity to idle on completion
                update_worker_activity(
                    self.request.id, 
                    'idle', 
                    'idle',
                    details={'result_status': 'success'}
                )
                
                return result
            except Exception as e:
                # Update activity to error on failure
                update_worker_activity(
                    self.request.id, 
                    activity_type, 
                    'error',
                    details={'error': str(e)}
                )
                raise
        return wrapper
    return decorator

@shared_task(base=LoggingTask, bind=True)
def verify_celery_connection(self):
    """
    Tâche simple pour vérifier que Celery fonctionne
    Cette tâche peut être appelée de n'importe où dans l'application
    pour confirmer que les workers Celery sont opérationnels
    """
    try:
        hostname = socket.gethostname()
        worker_name = self.request.hostname if hasattr(self.request, 'hostname') else 'unknown'
        
        # Information simple mais directe
        response = {
            "status": "success",
            "message": f"Connexion Celery vérifiée avec succès depuis {hostname}",
            "worker": worker_name,
            "timestamp": timezone.now().isoformat()
        }
        
        # Ajout d'information du worker si possible
        try:
            from celery.app.control import Inspect
            from celery import current_app
            
            inspect = Inspect(app=current_app)
            active_tasks = inspect.active()
            
            if active_tasks:
                active_tasks_count = sum(len(tasks) for tasks in active_tasks.values())
                response["active_tasks"] = active_tasks_count
        except Exception as e:
            logger.warning(f"Impossible de récupérer des informations supplémentaires sur Celery: {str(e)}")
        
        # Log simple
        logger.info(f"Vérification Celery réussie: {json.dumps(response)}")
        return response
    except Exception as e:
        logger.error(f"Erreur lors de la vérification Celery: {str(e)}")
        return {
            "status": "error",
            "message": f"Erreur lors de la vérification Celery: {str(e)}",
            "timestamp": timezone.now().isoformat()
        }

@shared_task(base=LoggingTask, bind=True)
@track_scraping_activity('scraping')
def start_structure_scrape(self, structure_id):
    """Start a manual scrape for a structure with detailed logging"""
    try:
        # Importations à l'intérieur de la fonction pour éviter les importations circulaires
        from django.utils import timezone
        from core.models import ScrapingStructure, ScrapingJob
        from .models import ScrapingTask, ScrapingLog
        
        logger.info(f"SCRAPER: Démarrage du scraping manuel pour la structure {structure_id}")
        logger.info(f"SCRAPER: Mode de fonctionnement: {'SIMULATION' if USING_SIMULATION else 'PRODUCTION avec Celery'}")
        
        # Get the structure
        try:
            structure = ScrapingStructure.objects.get(id=structure_id)
        except ScrapingStructure.DoesNotExist:
            logger.error(f"SCRAPER: Structure avec ID {structure_id} introuvable")
            raise ValueError(f"Structure with id {structure_id} does not exist")
        
        # Create a job for this manual scrape
        job = ScrapingJob.objects.create(
            user=structure.user,
            structure=structure,
            name=f"Manual scrape: {structure.name} - {timezone.now().strftime('%Y-%m-%d %H:%M')}",
            search_query=f"manual_{structure.name}",
            status='pending',
            schedule_type='manual'
        )
        
        logger.info(f"SCRAPER: Job {job.id} créé pour la structure '{structure.name}'")
        
        # Create a task for the job
        task = ScrapingTask.objects.create(
            job=job,
            status='initializing',
            celery_task_id=self.request.id  # Store the Celery task ID
        )
        
        # Log the creation of the task
        ScrapingLog.objects.create(
            task=task,
            log_type='info',
            message=f"SCRAPER: Tâche de scraping manuelle créée pour la structure: {structure.name}",
            details={
                "structure_id": structure.id, 
                "job_id": job.id,
                "mode": "SIMULATION" if USING_SIMULATION else "PRODUCTION"
            }
        )
        
        # Start the task
        job.status = 'running'
        job.save()
        
        logger.info(f"SCRAPER: Démarrage de la tâche {task.id} pour le job {job.id}")
        
        # Run the scraping task asynchronously
        run_scraping_task.delay(task.id)
        
        return {
            "status": "success",
            "task_id": task.id,
            "job_id": job.id,
            "mode": "SIMULATION" if USING_SIMULATION else "PRODUCTION"
        }
    except Exception as e:
        logger.error(f"SCRAPER ERROR: Erreur lors du démarrage du scraping: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "mode": "SIMULATION" if USING_SIMULATION else "PRODUCTION"
        }

@shared_task
def check_user_agents():
    """Check and manage user scraping agents"""
    # Skip if automatic scraping is disabled
    if not AUTOMATIC_SCRAPING_ENABLED:
        logger.info("SCRAPER: Scraping automatique désactivé, tâche check_user_agents ignorée")
        return
        
    # Importations à l'intérieur de la fonction pour éviter les importations circulaires
    from core.models import CustomUser
    
    logger.info(f"SCRAPER: Vérification des agents utilisateur (mode {'SIMULATION' if USING_SIMULATION else 'PRODUCTION'})")
    
    # Get all users with active jobs
    users = CustomUser.objects.filter(
        scraping_jobs__status__in=['pending', 'running']
    ).distinct()

    user_count = users.count()
    logger.info(f"SCRAPER: {user_count} utilisateurs avec des tâches actives")

    for user in users:
        # Check if user has reached their daily quota
        profile = user.profile
        if not profile.unlimited_leads:
            profile.reset_daily_leads()
            if not profile.can_access_leads:
                logger.info(f"SCRAPER: L'utilisateur {user.email} a atteint son quota quotidien")
                continue

        # Get user's active jobs
        active_jobs = user.scraping_jobs.filter(
            status__in=['pending', 'running']
        )
        
        logger.info(f"SCRAPER: Utilisateur {user.email} - {active_jobs.count()} tâches actives, "
                   f"quota: {profile.leads_used}/{profile.leads_quota} "
                   f"{'(illimité)' if profile.unlimited_leads else ''}")

        for job in active_jobs:
            # Check if job needs to be processed
            if job.status == 'pending':
                logger.info(f"SCRAPER: Démarrage du job {job.id} pour l'utilisateur {user.email}")
                start_job.delay(job.id)
            elif job.status == 'running':
                logger.info(f"SCRAPER: Vérification du job {job.id} pour l'utilisateur {user.email}")
                check_job_progress.delay(job.id)

@shared_task
def start_job(job_id):
    """Start a new scraping job"""
    try:
        # Importations à l'intérieur de la fonction pour éviter les importations circulaires
        from core.models import ScrapingJob
        from .models import ScrapingTask, ScrapingLog
        
        job = ScrapingJob.objects.get(id=job_id)
        logger.info(f"SCRAPER: Initialisation du job {job_id} - '{job.name}' "
                   f"(mode {'SIMULATION' if USING_SIMULATION else 'PRODUCTION'})")
        
        # Create new task
        task = ScrapingTask.objects.create(
            job=job,
            status='initializing',
            current_step='Initialisation de la tâche'
        )

        # Add initial log
        ScrapingLog.objects.create(
            task=task,
            log_type='info',
            message=f"SCRAPER: Tâche de scraping initialisée pour '{job.name}'",
            details={
                "mode": "SIMULATION" if USING_SIMULATION else "PRODUCTION",
                "user_email": job.user.email,
                "structure": job.structure.name if job.structure else "Aucune structure"
            }
        )

        logger.info(f"SCRAPER: Lancement de la tâche {task.id} pour le job {job_id}")
        
        # Start the actual scraping process
        run_scraping_task.delay(task.id)
        
        # Update job status
        job.status = 'running'
        job.save()

    except Exception as e:
        logger.error(f"SCRAPER ERROR: Erreur lors du démarrage du job {job_id}: {str(e)}", exc_info=True)

@shared_task(bind=True, base=LoggingTask)
@track_scraping_activity('scraping')
def run_scraping_task(self, task_id):
    """
    Exécute une tâche de scraping avec une exploration améliorée
    """
    # Garde le log critique pour faciliter le débogage
    logger.critical(f"!!!!!!!!!! DÉBUT DE RUN_SCRAPING_TASK POUR TÂCHE {task_id} !!!!!!!!!")
    
    logger.info(f"=== DÉBUT DE RUN_SCRAPING_TASK POUR TÂCHE {task_id} ===")
    logger.info(f"Mode d'exécution: {'SIMULATION' if USING_SIMULATION else 'PRODUCTION'}")
    
    try:
        # Import models inside
        from .models import ScrapingTask, ScrapingLog, ScrapedSite, ScrapingResult
        from core.utils.ai_utils import AIManager
        from utils.serpapi import get_serp_results
        from bs4 import BeautifulSoup
        from urllib.parse import urlparse, urljoin
        
        # Récupération de la tâche
        try:
            if isinstance(task_id, str) and task_id.isdigit():
                task_id = int(task_id)
            
            logger.info(f"Recherche de la tâche avec ID: {task_id}")
            task = ScrapingTask.objects.get(id=task_id)
            logger.info(f"Tâche trouvée: {task} (Job: {task.job.name})")
        except ScrapingTask.DoesNotExist:
            logger.error(f"Tâche {task_id} introuvable")
            return {"status": "failed", "error": f"Task with id {task_id} does not exist"}
        except Exception as e:
            logger.error(f"Erreur lors de la récupération de la tâche {task_id}: {str(e)}", exc_info=True)
            return {"status": "failed", "error": f"Error retrieving task: {str(e)}"}
        
        # Mise à jour du statut de la tâche
        task.celery_task_id = self.request.id  # Rétabli l'ID Celery
        task.status = 'initializing'
        task.current_step = "Initialisation de la tâche..."
        task.save(update_fields=['celery_task_id', 'status', 'current_step'])
        
        logger.info(f"Statut de la tâche mis à jour: {task.status}, Étape: {task.current_step}")
        
        # Log du démarrage de la tâche
        ScrapingLog.objects.create(
            task=task,
            log_type='info',
            message=f"Tâche démarrée sur {socket.gethostname()}",
            details={
                "task_id": self.request.id,
                "worker": socket.gethostname(),
                "mode": "PRODUCTION"
            }
        )
        
        # Récupération du job et de la structure
        job = task.job
        structure = job.structure
        
        logger.info(f"Job trouvé: {job.name} (ID: {job.id})")
        logger.info(f"Structure associée: {structure.name} (ID: {structure.id})")
        
        # CRITICAL FIX: Ensure job has a valid user for lead creation
        if not job.user:
            logger.error(f"❌ CRITICAL ERROR: Job {job.id} has no associated user. Cannot create leads without a user.")
            # Try to get user from structure if available
            if structure and structure.user:
                logger.info(f"🔄 Using user from structure instead: {structure.user.id}")
                job.user = structure.user
                job.save(update_fields=['user'])
            else:
                logger.error(f"❌ Cannot proceed without a valid user for job {job.id}. Using system user as fallback.")
                from django.contrib.auth import get_user_model
                User = get_user_model()
                system_user = User.objects.filter(is_superuser=True).first()
                if system_user:
                    job.user = system_user
                    job.save(update_fields=['user'])
                    logger.warning(f"⚠️ Using system user {system_user.id} as fallback for job {job.id}")
                else:
                    logger.error(f"❌ No fallback user available. Lead creation will fail.")
        else:
            logger.info(f"✅ Job {job.id} has valid user: {job.user.id}")
        
        # --- FIX: Use the actual job search query ---
        actual_search_query = job.search_query
        # Optional: Fallback if manual query pattern detected
        if actual_search_query and actual_search_query.startswith("manual_"):
            logger.warning(f"Detected manual query pattern '{actual_search_query}'. Falling back to structure name: '{structure.name}'")
            actual_search_query = structure.name
        
        # Ensure we have a query to use
        if not actual_search_query:
             logger.error(f"ERREUR: Aucune requête de recherche valide trouvée pour le job {job.id}. Utilisation du nom du job comme fallback.")
             actual_search_query = job.name
        
        # Initialisation de l'AIManager
        logger.info("Initialisation de l'AIManager")
        ai_manager = AIManager()
        
        # Générer des requêtes de recherche supplémentaires basées sur la requête principale
        logger.info(f"Génération de requêtes de recherche supplémentaires à partir de: '{actual_search_query}'")
        
        # Génération de variantes de requêtes avec MistralAI
        query_generation_prompt = f"""
        Génère 10 requêtes de recherche pertinentes pour trouver des informations et des contacts concernant: "{actual_search_query}".
        Les requêtes doivent être diversifiées pour couvrir différents aspects et maximiser les chances de trouver des leads.
        Le but est de trouver des entreprises, leurs décideurs ou des professionnels associés à ce secteur.
        Format requis: liste JSON avec seulement les requêtes, pas d'autres explications.
        """
        
        search_queries = [actual_search_query]  # Inclure la requête originale
        
        try:
            # Générer des requêtes avec MistralAI - direct call 
            query_variations = ai_manager.generate_search_variations(query_generation_prompt)
            if isinstance(query_variations, list) and len(query_variations) > 0:
                search_queries.extend(query_variations[:10])  # Limiter à 10 requêtes supplémentaires
                logger.info(f"Requêtes de recherche générées: {len(search_queries)} au total")
                logger.debug(f"Requêtes: {search_queries}")
            else:
                logger.warning("Impossible de générer des requêtes supplémentaires, utilisation de la requête principale uniquement")
        except Exception as e:
            logger.error(f"Erreur lors de la génération des requêtes: {str(e)}")
        
        # Get or create structure usage tracking
        task.status = 'crawling'
        task.current_step = "Récupération des résultats de recherche..."
        task.save(update_fields=['status', 'current_step'])
        
        # Mise à jour de l'activité du worker
        update_worker_activity(
            self.request.id,
            'scraping',
            'running',
            current_url=f"search:{actual_search_query}",
            details={
                "task_id": task.id,
                "structure_name": structure.name if structure else "No structure",
                "step": "crawling"
            }
        )
        
        # Récupérer les résultats SERP pour chaque requête (3 pages pour chaque requête)
        all_serp_results = []
        
        for query_index, query in enumerate(search_queries[:5]):  # Limiter à 5 requêtes pour éviter timeout
            logger.info(f"Traitement de la requête {query_index+1}/{len(search_queries[:5])}: '{query}'")
            
            for page in range(1, 4):  # 3 pages par requête
                logger.info(f"Récupération des résultats SERP pour '{query}' - Page {page}")
                try:
                    # Obtenir les résultats SERP pour cette requête et cette page
                    page_results = get_serp_results(query, page=page)
                    if page_results:
                        logger.info(f"{len(page_results)} résultats trouvés pour '{query}' - Page {page}")
                        all_serp_results.extend(page_results)
                        
                        # Mettre à jour le statut pour montrer la progression
                        task.current_step = f"Analyse des résultats de recherche {query_index+1}/{len(search_queries[:5])} - Page {page}/3"
                        task.save(update_fields=['current_step'])
                    else:
                        logger.warning(f"Aucun résultat trouvé pour '{query}' - Page {page}")
                        break  # Passer à la requête suivante si pas de résultats
                except Exception as e:
                    logger.error(f"Erreur lors de la récupération des résultats SERP pour '{query}' - Page {page}: {str(e)}")
                    continue
        
        # Dédupliquer les résultats par URL
        unique_results = {}
        for result in all_serp_results:
            if result.get('url') and result.get('url') not in unique_results:
                unique_results[result.get('url')] = result
        
        all_serp_results = list(unique_results.values())
        logger.info(f"{len(all_serp_results)} résultats SERP uniques trouvés au total")
        
        # Analyser les résultats SERP pour trouver les sites les plus pertinents
        logger.info("Analyse des résultats SERP avec MistralAI pour déterminer les priorités")
        serp_analysis = {"priority_links": []}
        
        try:
            # Préparation de la structure JSON
            initial_json_structure = {"priority_links": [], "explored_links": []}
            # Change from asyncio.run to direct call
            serp_analysis = ai_manager.analyze_serp_results(all_serp_results, initial_json_structure)
            logger.info("Analyse SERP terminée.")
            logger.debug(f"Résultat complet de l'analyse SERP: {json.dumps(serp_analysis, indent=2, ensure_ascii=False)}")
        except Exception as ai_error:
            logger.error(f"Erreur pendant l'analyse SERP par l'IA: {ai_error}", exc_info=True)
        
        # Créer la liste de sites à explorer (prioritaires d'abord, puis autres)
        priority_links = serp_analysis.get("priority_links", [])
        other_links = [result.get('url') for result in all_serp_results if result.get('url') not in priority_links]
        
        all_links_to_explore = priority_links + other_links
        
        # Dédupliquer et nettoyer les liens
        urls_to_explore = []
        explored_urls = set()
        
        for url in all_links_to_explore:
            if url and url not in explored_urls:
                parsed_url = urlparse(url)
                # Vérifier si le lien est valide
                if parsed_url.scheme and parsed_url.netloc:
                    urls_to_explore.append(url)
                    explored_urls.add(url)
        
        logger.info(f"{len(urls_to_explore)} URLs uniques à explorer")
        
        # Mise à jour du statut de la tâche
        task.current_step = f"Exploration des sites web ({len(urls_to_explore)} au total)..."
        task.save(update_fields=['current_step'])
        
        # Définir les sites à scraper
        sites_to_scrape = []
        
        for url in urls_to_explore:
            domain = urlparse(url).netloc
            site, created = ScrapedSite.objects.get_or_create(
                url=url,
                structure=structure,
                defaults={'domain': domain, 'last_scraped': None}
            )
            sites_to_scrape.append(site)
            if created:
                ScrapingLog.objects.create(
                    task=task, log_type='info',
                    message=f"Nouveau site découvert: {url}",
                    details={"domain": domain}
                )
        
        logger.info(f"{len(sites_to_scrape)} sites prêts pour le scraping")
        
        # Fonction pour déterminer l'action suivante après l'analyse d'une page
        def analyze_next_action(html_content, json_structure, url):
            """Détermine l'action suivante après l'analyse d'une page HTML"""
            if not html_content or len(html_content.strip()) < 100:
                logger.warning(f"Contenu HTML vide ou trop court pour {url}")
                return {"action": "go_next_page"}
            
            # Si la page a déjà donné des leads, continuer avec d'autres pages
            if json_structure.get("contacts") and len(json_structure.get("contacts")) > 0:
                logger.info(f"Contacts trouvés sur {url}, passage à la page suivante")
                return {"action": "go_next_page"}
            
            # Trouver des liens pertinents sur la page actuelle
            try:
                soup = BeautifulSoup(html_content, 'html.parser')
                all_links = soup.find_all('a', href=True)
                
                # Préparation du prompt pour MistralAI
                links_context = "\n".join([f"{i+1}. {link.text.strip()[:50]} - {link['href']}" 
                                    for i, link in enumerate(all_links[:20]) if link.text.strip()])
                
                prompt = f"""
                Tu es un assistant de scraping intelligent. Voici le contexte actuel:
                
                URL actuelle: {url}
                
                Objectif: Trouver des leads pour "{structure.name}".
                
                Liens trouvés sur cette page:
                {links_context}
                
                Décide quelle action prendre:
                1. "click_on_link" - si un lien spécifique sur cette page semble prometteur pour trouver des contacts
                2. "go_next_page" - si aucun lien n'est pertinent ou si la page actuelle ne contient pas d'information utile
                
                Réponds au format JSON uniquement:
                {{
                    "action": "click_on_link" ou "go_next_page",
                    "href": "URL complète du lien à suivre" (seulement si action est click_on_link)
                }}
                """
                
                next_action = ai_manager.determine_next_action(prompt)
                logger.debug(f"Résultat de l'analyse de l'action suivante: {next_action}")
                
                if isinstance(next_action, dict) and next_action.get("action") == "click_on_link" and next_action.get("href"):
                    # Normaliser l'URL relative si nécessaire
                    href = next_action.get("href")
                    if not urlparse(href).netloc:
                        href = urljoin(url, href)
                    
                    logger.info(f"Action suivante recommandée: explorer {href}")
                    return {"action": "click_on_link", "href": href}
                
                return {"action": "go_next_page"}
                
            except Exception as e:
                logger.error(f"Erreur lors de l'analyse de l'action suivante: {str(e)}", exc_info=True)
                return {"action": "go_next_page"}
        
        # Explorer chaque site avec un mécanisme de navigation intelligente
        leads_found = 0
        max_pages_to_explore = 150  # Limite pour éviter exploration infinie
        explored_pages = set()
        
        for site_index, site in enumerate(sites_to_scrape[:50]):  # Limiter à 50 sites pour éviter timeout
            current_url = site.url
            pages_explored_for_site = 0
            max_pages_per_site = 5  # Max 5 pages par site pour diversifier les sources
            
            # Structure JSON pour stocker les informations du site
            site_json_structure = {
                "site_info": {
                    "name": site.domain,
                    "url": site.url
                },
                "contacts": [],
                "meta_data": {
                    "explored_links": [site.url],
                    "priority_links": []
                }
            }
            
            logger.info(f"Début de l'exploration du site {site_index+1}/{len(sites_to_scrape[:50])}: {site.url}")
            task.current_step = f"Exploration du site {site_index+1}/{len(sites_to_scrape[:50])}: {site.domain}"
            task.save(update_fields=['current_step'])
            
            while pages_explored_for_site < max_pages_per_site and len(explored_pages) < max_pages_to_explore:
                if current_url in explored_pages:
                    logger.info(f"URL déjà explorée: {current_url}, passage à une autre URL")
                    break
                
                logger.info(f"Exploration de l'URL: {current_url}")
                explored_pages.add(current_url)
                site_json_structure["meta_data"]["explored_links"].append(current_url)
                
                try:
                    # Récupération et analyse du contenu HTML
                    response = requests.get(current_url, timeout=30)
                    response.raise_for_status()
                    html_content = response.text
                    
                    logger.info(f"Contenu HTML récupéré de {current_url} ({len(html_content)} caractères)")
                    
                    # Analyse du contenu HTML avec MistralAI
                    extraction_objective = f"Extraire toutes les informations de contact pertinentes pour {structure.name}. Chercher également toute information commerciale utile."
                    
                    # Get the structure schema if available
                    structure_schema = None
                    if structure and hasattr(structure, 'structure'):
                        structure_schema = structure.structure
                    
                    # Pass structure schema to analyze_html_content for better extraction results
                    html_analysis = ai_manager.analyze_html_content(
                        html_content, 
                        extraction_objective, 
                        site_json_structure,
                        structure_schema=structure_schema
                    )
                    
                    logger.info(f"Analyse HTML terminée pour {current_url}")
                    logger.debug(f"Résultat de l'analyse HTML: {json.dumps(html_analysis, indent=2)}")
                    
                    # CRITICAL FIX: If 'nom' field exists but no company fields, map 'nom' to 'nom_entreprise'
                    if 'nom' in html_analysis and html_analysis['nom'] and not any(field in html_analysis for field in ['nom_entreprise', 'company', 'entreprise']):
                        html_analysis['nom_entreprise'] = html_analysis['nom']
                        logger.info(f"Early mapping: Using 'nom' as company name: {html_analysis['nom']}")
                    
                    # DIRECT LEAD CREATION FROM CUSTOM STRUCTURE
                    # This is the critical fix - explicitly process custom structure data
                    if 'nom_entreprise' in html_analysis and isinstance(html_analysis, dict):
                        logger.info(f"🔍 Processing custom structure data for lead creation: {html_analysis.get('nom_entreprise')}")
                        
                        # Create a ScrapingResult from the custom structure data
                        try:
                            scraping_result = ScrapingResult.objects.create(
                                task=task,
                                lead_data=html_analysis,
                                source_url=current_url
                            )
                            
                            # Log the creation of the scraping result
                            logger.info(f"✅ Created scraping result with ID: {scraping_result.id} for company: {html_analysis.get('nom_entreprise')}")
                            
                            # Create a lead from the scraping result
                            lead = create_lead_from_result(scraping_result, job)
                            
                            if lead:
                                logger.info(f"✅ Successfully created lead ID: {lead.id} for company: {html_analysis.get('nom_entreprise')}")
                                leads_found += 1
                            else:
                                logger.warning(f"❌ Failed to create lead for company: {html_analysis.get('nom_entreprise')}")
                        except Exception as e:
                            logger.error(f"❌ Error creating lead from HTML analysis: {str(e)}", exc_info=True)
                    # Handle custom structure format with fields that have spaces in names 
                    elif 'Nom de l\'entreprise' in html_analysis and isinstance(html_analysis, dict):
                        # This is a custom structure with field names that have spaces
                        company_name = html_analysis.get('Nom de l\'entreprise')
                        logger.info(f"🔍 Processing custom structure data with spaced field names for: {company_name}")
                        
                        # Log all the fields in the custom structure for debugging
                        logger.debug(f"Custom structure fields: {list(html_analysis.keys())}")
                        
                        # Create a ScrapingResult from the custom structure data
                        try:
                            scraping_result = ScrapingResult.objects.create(
                                task=task,
                                lead_data=html_analysis,
                                source_url=current_url
                            )
                            
                            # Log the creation of the scraping result
                            logger.info(f"✅ Created scraping result with ID: {scraping_result.id} for company: {company_name}")
                            
                            # Create a lead from the scraping result
                            lead = create_lead_from_result(scraping_result, job)
                            
                            if lead:
                                logger.info(f"✅ Successfully created lead ID: {lead.id} for company: {company_name}")
                                leads_found += 1
                            else:
                                logger.warning(f"❌ Failed to create lead for company: {company_name}, investigating...")
                                # Try to diagnose the issue
                                try:
                                    from core.models import Lead
                                    # Check if the user has reached their lead limit
                                    if hasattr(job.user, 'profile') and hasattr(job.user.profile, 'can_access_leads'):
                                        profile = job.user.profile
                                        if not profile.can_access_leads:
                                            logger.error(f"⚠️ User {job.user.id} has reached their lead limit. Lead creation skipped.")
                                        else:
                                            logger.info(f"✅ User {job.user.id} has NOT reached lead limit (used: {profile.leads_used}, quota: {profile.leads_quota})")
                                except Exception as profile_error:
                                    logger.error(f"Error checking user profile limits: {profile_error}")
                        except Exception as e:
                            logger.error(f"❌ Error creating lead from custom structure: {str(e)}", exc_info=True)
                    
                    # Generic check for any custom structure with a company-like field
                    elif isinstance(html_analysis, dict) and len(html_analysis) > 0:
                        # Try to identify if this is a custom structure based on field naming patterns
                        logger.info(f"🔎 Checking if data is a custom structure format: {list(html_analysis.keys())}")
                        
                        # Check for company name in various possible formats
                        company_field_candidates = [
                            'nom_entreprise', 'company', 'entreprise', 'société', 'organization',
                            'Nom de l\'entreprise', 'nom de l entreprise', 'nom de la société',
                            'Company', 'Organization', 'Entreprise'
                        ]
                        
                        # Also check for field names containing 'company' or 'entreprise'
                        for key in html_analysis.keys():
                            if isinstance(key, str) and ('entreprise' in key.lower() or 'company' in key.lower()):
                                if key not in company_field_candidates:
                                    company_field_candidates.append(key)
                        
                        # Find the first valid company name field
                        company_name = None
                        company_field = None
                        
                        for field in company_field_candidates:
                            if field in html_analysis and html_analysis[field]:
                                company_name = html_analysis[field]
                                company_field = field
                                break
                        
                        if company_name:
                            logger.info(f"✅ Found company name '{company_name}' in field '{company_field}'")
                            logger.info(f"🔍 Processing generic custom structure data for: {company_name}")
                            
                            # Check if we have enough data fields (arbitrary threshold)
                            if len(html_analysis) >= 3:
                                try:
                                    # Create a normalized copy of the data with consistent field names
                                    normalized_data = {}
                                    for key, value in html_analysis.items():
                                        # Replace spaces with underscores and lowercase
                                        normalized_key = key.replace(' ', '_').replace('\'', '_').lower()
                                        normalized_data[normalized_key] = value
                                        
                                        # Add a mapping for standard fields
                                        if 'entreprise' in normalized_key or 'company' in normalized_key:
                                            normalized_data['nom_entreprise'] = value
                                            
                                    # Create the ScrapingResult
                                    scraping_result = ScrapingResult.objects.create(
                                        task=task,
                                        lead_data=normalized_data,
                                        source_url=current_url
                                    )
                                    
                                    logger.info(f"✅ Created scraping result with ID: {scraping_result.id} for company: {company_name}")
                                    
                                    # Create a lead
                                    lead = create_lead_from_result(scraping_result, job)
                                    
                                    if lead:
                                        logger.info(f"✅ Successfully created lead ID: {lead.id} for company: {company_name}")
                                        leads_found += 1
                                    else:
                                        logger.warning(f"❌ Failed to create lead for company: {company_name}")
                                        logger.debug(f"Normalized lead data: {normalized_data}")
                                except Exception as e:
                                    logger.error(f"❌ Error creating lead from generic custom structure: {str(e)}", exc_info=True)
                            else:
                                logger.warning(f"⚠️ Not enough fields in custom structure data: {len(html_analysis)} fields")
                        else:
                            logger.warning(f"⚠️ No company name found in potential custom structure: {list(html_analysis.keys())}")
                    
                    # Process the AI analysis results for contacts array format (if present)
                    leads_processed = False
                    
                    # Check if industry/sector field is missing but required
                    if structure.structure and "secteur_activite" in [field.get('name') for field in structure.structure if field.get('required', True)]:
                        if 'secteur_activite' in html_analysis and not html_analysis['secteur_activite']:
                            # The sector field exists but is empty, try a dedicated analysis to find it
                            logger.warning("Missing sector field detected, attempting targeted extraction...")
                            
                            try:
                                # Create a specialized prompt for industry detection
                                company_name = html_analysis.get('nom_entreprise', html_analysis.get('company', site.domain))
                                company_desc = html_analysis.get('description', '')
                                
                                # Get the industry analysis
                                industry_messages = [
                                    {"role": "system", "content": "You are an expert in business analysis and industry classification."},
                                    {"role": "user", "content": f"""
Analyze this HTML content and determine the industry sector for this company:

COMPANY NAME: {company_name}
COMPANY DESCRIPTION: {company_desc}

HTML CONTENT:
{html_content[:8000]}

I need ONLY the industry or business sector. Return ONLY a JSON object like this:
{{"secteur_activite": "Technology"}}

Use specific industry categories like Technology, Healthcare, Manufacturing, Financial Services, 
Education, Media, Retail, etc. Make your best determination based on the content.
If you're unsure but can make an educated guess, add "Probable: " prefix.
"""}
                                ]
                                
                                # Get the industry analysis
                                industry_result = ai_manager.send_mistral_request(industry_messages, model="mistral-large-latest")
                                
                                # If successful, update the original analysis
                                if isinstance(industry_result, dict) and 'secteur_activite' in industry_result and industry_result['secteur_activite']:
                                    html_analysis['secteur_activite'] = industry_result['secteur_activite']
                                    logger.info(f"Successfully extracted industry sector: {industry_result['secteur_activite']}")
                                elif isinstance(industry_result, str):
                                    # Try to extract JSON from string if needed
                                    # re and json modules are already imported at the top of the file
                                    
                                    # Try to find JSON pattern in the response
                                    json_match = re.search(r'\{.*?"secteur_activite".*?:.*?".*?".*?\}', industry_result)
                                    if json_match:
                                        try:
                                            extracted_json = json.loads(json_match.group(0))
                                            if 'secteur_activite' in extracted_json and extracted_json['secteur_activite']:
                                                html_analysis['secteur_activite'] = extracted_json['secteur_activite']
                                                logger.info(f"Extracted industry from text response: {extracted_json['secteur_activite']}")
                                        except:
                                            logger.warning("Failed to parse extracted industry JSON")
                            except Exception as e:
                                logger.warning(f"Error during targeted industry extraction: {str(e)}")
                    
                    # Mettre à jour la structure JSON avec les nouvelles informations
                    if html_analysis and isinstance(html_analysis, dict):
                        # Extraire et stocker les contacts
                        if "contacts" in html_analysis and html_analysis["contacts"]:
                            for contact in html_analysis["contacts"]:
                                # Vérifier si le contact est valide et non-dupliqué
                                leads_found = process_contact(contact, task, current_url, job, leads_found)
                    
                    # Mettre à jour les statistiques de la tâche
                    task.pages_explored += 1
                    task.leads_found = leads_found
                    task.unique_leads = int(leads_found * 0.8)  # Estimation de l'unicité
                    task.save(update_fields=['pages_explored', 'leads_found', 'unique_leads'])
                    
                    # Déterminer l'action suivante
                    next_action = analyze_next_action(html_content, site_json_structure, current_url)
                    
                    if next_action.get("action") == "click_on_link" and next_action.get("href"):
                        # Suivre le lien recommandé
                        current_url = next_action.get("href")
                        logger.info(f"Navigation vers: {current_url}")
                    else:
                        # Passer au site suivant
                        logger.info(f"Fin de l'exploration pour ce site, passage au suivant")
                        break
                    
                    pages_explored_for_site += 1
                    
                except requests.exceptions.RequestException as e:
                    logger.error(f"Erreur lors de la requête HTTP vers {current_url}: {str(e)}")
                    break
                except Exception as e:
                    logger.error(f"Erreur lors de l'exploration de {current_url}: {str(e)}", exc_info=True)
                    break
            
            # Mise à jour de la date de dernier scraping du site
            site.last_scraped = timezone.now()
            site.save(update_fields=['last_scraped'])
        
        # Marquer la tâche comme terminée
        task.status = 'completed'
        task.current_step = "Tâche terminée avec succès"
        task.completion_time = timezone.now()
        task.save()
        logger.info(f"Tâche {task_id} terminée avec succès")
        
        return {"status": "success", "task_id": task_id, "leads_found": leads_found}
        
    except Exception as e:
        logger.error(f"Erreur majeure dans run_scraping_task: {str(e)}", exc_info=True)
        logger.error(f"Traceback complet: {traceback.format_exc()}")
        try:
            if 'task' in locals():
                task.status = 'failed'
                task.current_step = f"Erreur majeure: {str(e)}"
                task.save()
                ScrapingLog.objects.create(
                    task=task, log_type='error',
                    message=f"Erreur majeure lors de l'exécution de la tâche: {str(e)}",
                    details={"error": str(e), "traceback": traceback.format_exc()}
                )
            else:
                logger.error("Impossible de mettre à jour le statut de la tâche: variable 'task' non définie.")
        except Exception as save_error:
            logger.error(f"Erreur lors de la mise à jour du statut de la tâche après erreur majeure: {str(save_error)}")
        
        return {"status": "failed", "error": str(e)}

def validate_contact(contact, structure_schema=None):
    """Vérifie si un contact est valide et mérite d'être enregistré"""
    # This function is kept for backwards compatibility
    # It now calls the more comprehensive is_valid_contact function
    return is_valid_contact(contact, structure_schema)

# Helper function to handle contact extraction and lead creation
def process_contact(contact, task, current_url, job, leads_count=0):
    """Process a contact: validate, create result and lead, update stats"""
    logger.info(f"Processing contact from URL: {current_url}")
    logger.debug(f"Contact data to process: {contact}")
    
    try:
        # Get the structure schema from the job
        structure_schema = None
        if job.structure and hasattr(job.structure, 'structure'):
            structure_schema = job.structure.structure
            logger.debug(f"Using structure schema from job {job.id}: {structure_schema}")
        
        # Validate contact
        is_valid = is_valid_contact(contact, structure_schema)
        logger.info(f"Contact validation result: {'valid' if is_valid else 'invalid'}")
        
        if not is_valid:
            logger.warning(f"Contact skipped: Invalid contact data from {current_url}")
            return leads_count
            
        # Create a scraping result for valid contact
        logger.info(f"Creating scraping result for valid contact from {current_url}")
        try:
            scraping_result = ScrapingResult.objects.create(
                task=task,
                lead_data=contact,
                source_url=current_url
            )
            logger.info(f"Scraping result created with ID: {scraping_result.id}")
        except Exception as result_error:
            logger.error(f"❌ Failed to create scraping result: {str(result_error)}", exc_info=True)
            return leads_count
        
        # Log the contact found
        try:
            contact_name = contact.get('nom', contact.get('name', contact.get('nom_contact', 'Sans nom')))
            ScrapingLog.objects.create(
                task=task,
                log_type='info',
                message=f"Contact trouvé: {contact_name}",
                details=contact
            )
            logger.debug(f"Created scraping log for contact: {contact_name}")
        except Exception as log_error:
            logger.warning(f"Could not create scraping log: {str(log_error)}")
        
        # Create a lead from the result
        logger.info(f"Attempting to create lead from scraping result {scraping_result.id}")
        lead = create_lead_from_result(scraping_result, job)
        
        if lead:
            logger.info(f"✅ Lead created successfully: {lead.name} (ID: {lead.id})")
            leads_count += 1
        else:
            logger.warning(f"⚠️ Lead creation failed or was skipped for scraping result {scraping_result.id}")
            
        return leads_count
    except Exception as e:
        logger.error(f"❌ Error during contact processing: {str(e)}", exc_info=True)
        return leads_count

@shared_task
def check_job_progress(job_id):
    """Check progress of a running job"""
    try:
        # Importations à l'intérieur de la fonction pour éviter les importations circulaires
        from core.models import ScrapingJob
        from .models import ScrapingTask, ScrapingLog
        
        job = ScrapingJob.objects.get(id=job_id)
        active_task = job.scraping_tasks.filter(status__in=['initializing', 'crawling', 'extracting', 'processing']).first()
        
        # Si pas de tâche active dans scraping_tasks, essayons avec core_tasks
        if not active_task:
            active_task = job.core_tasks.filter(status__in=['initializing', 'crawling', 'extracting', 'processing']).first()
        
        if not active_task:
            # No active task, job might be stuck
            job.status = 'failed'
            job.save()
            
            # Créer un log même sans tâche active
            logger.error(f"Job {job_id} bloqué - aucune tâche active trouvée")
            return

        # Check if task has been running too long
        if active_task.duration > 3600:  # 1 hour max
            active_task.status = 'failed'
            active_task.error_message = "Task exceeded maximum duration"
            active_task.completion_time = timezone.now()
            active_task.save()
            
            ScrapingLog.objects.create(
                task=active_task,
                log_type='error',
                message="Task terminated: exceeded maximum duration"
            )
            
            job.status = 'failed'
            job.save()

    except Exception as e:
        logger.error(f"Error checking job progress {job_id}: {str(e)}", exc_info=True)

@shared_task
def cleanup_old_tasks():
    """Clean up old completed tasks"""
    try:
        # Importations à l'intérieur de la fonction pour éviter les importations circulaires
        from .models import ScrapingTask
        
        # Delete tasks older than 7 days
        old_date = timezone.now() - timedelta(days=7)
        ScrapingTask.objects.filter(
            status__in=['completed', 'failed'],
            completion_time__lt=old_date
        ).delete()
    except Exception as e:
        logger.error(f"Error cleaning up old tasks: {str(e)}", exc_info=True)

def get_next_site_to_scrape(scraped_sites, structure):
    """Get the next site to scrape based on various factors"""
    # First try to find a site that hasn't been scraped recently
    site = scraped_sites.filter(
        Q(last_scraped__lt=timezone.now() - timedelta(hours=24)) |
        Q(last_scraped__isnull=True)
    ).exclude(
        rate_limit_until__gt=timezone.now()
    ).order_by('last_scraped').first()

    if site:
        return site

    # If no site found, create a new one based on structure's scraping strategy
    # This is where you would implement your site discovery logic
    # For now, we'll just return None
    return None

def create_lead_from_result(scraping_result, job):
    """Create a Lead object from a ScrapingResult"""
    try:
        lead_data = scraping_result.lead_data
        logger.info(f"Creating lead from scraping result {scraping_result.id}: {lead_data}")
        
        # CRITICAL DEBUG: Validate job and user
        if not job:
            logger.error(f"❌ CRITICAL: No job provided for lead creation from result {scraping_result.id}")
            return None
            
        if not job.user:
            logger.error(f"❌ CRITICAL: Job {job.id} has no user for lead creation from result {scraping_result.id}")
            return None
            
        logger.info(f"✅ Job validation OK - Job ID: {job.id}, User ID: {job.user.id}")
        
        # Normalize field keys that have spaces by replacing spaces with underscores
        normalized_lead_data = {}
        for key, value in lead_data.items():
            # Replace spaces with underscores in keys
            normalized_key = key.replace(' ', '_').replace('\'', '_').lower() if isinstance(key, str) else key
            normalized_lead_data[normalized_key] = value
            # Log any key normalization that occurred
            if normalized_key != key:
                logger.info(f"Field name normalized: '{key}' → '{normalized_key}'")
        
        # Check for company name in normalized field names
        if 'nom_entreprise' not in normalized_lead_data and 'nom_de_l_entreprise' not in normalized_lead_data:
            # Try to find company name in normalized keys
            for key in normalized_lead_data.keys():
                if key in ['company', 'entreprise', 'société', 'organization']:
                    logger.info(f"Using alternate company field: {key} = {normalized_lead_data[key]}")
                    normalized_lead_data['nom_entreprise'] = normalized_lead_data[key]
                    break
                elif 'entreprise' in key or 'company' in key or 'organization' in key:
                    logger.info(f"Using fuzzy matched company field: {key} = {normalized_lead_data[key]}")
                    normalized_lead_data['nom_entreprise'] = normalized_lead_data[key]
                    break
                # Special case for 'nom' as company name (which happens in scraping logs)
                elif key == 'nom' and not any(k.startswith('nom_entreprise') for k in normalized_lead_data.keys()):
                    logger.info(f"Special case: Using 'nom' as company name: {normalized_lead_data[key]}")
                    normalized_lead_data['nom_entreprise'] = normalized_lead_data[key]
                    break
        
        # Check if we now have a company name
        company_name = normalized_lead_data.get('nom_entreprise', normalized_lead_data.get('company', None))
        if not company_name:
            logger.error(f"❌ No company name found in data: {normalized_lead_data.keys()}")
            # Try to extract from other fields as a last resort
            if 'nom_de_l_entreprise' in normalized_lead_data:
                company_name = normalized_lead_data['nom_de_l_entreprise']
                logger.info(f"Using nom_de_l_entreprise as company name: {company_name}")
                normalized_lead_data['nom_entreprise'] = company_name
            elif any(key.startswith('nom') for key in normalized_lead_data.keys()):
                possible_company_keys = [k for k in normalized_lead_data.keys() if k.startswith('nom')]
                for key in possible_company_keys:
                    if 'entreprise' in key.lower() and normalized_lead_data[key]:
                        company_name = normalized_lead_data[key]
                        logger.info(f"Using {key} as company name: {company_name}")
                        normalized_lead_data['nom_entreprise'] = company_name
                        break
        
        # Check for duplicates based on company name
        if company_name:
            from core.models import Lead
            
            # Check if a lead with this company name already exists for this user
            existing_leads = Lead.objects.filter(
                user=job.user,
                company=company_name
            )
            
            if existing_leads.exists():
                # Mark the scraping result as a duplicate
                scraping_result.is_duplicate = True
                scraping_result.save(update_fields=['is_duplicate'])
                
                # Update task duplicate count if possible
                try:
                    task = scraping_result.task
                    task.duplicate_leads += 1
                    task.save(update_fields=['duplicate_leads'])
                except Exception as e:
                    logger.warning(f"Could not update duplicate count for task: {str(e)}")
                
                logger.info(f"Duplicate lead detected for company: {company_name}. Skipping creation.")
                return existing_leads.first()
        
        structure_schema = {}
        if job.structure and job.structure.structure:
            structure_schema = job.structure.structure
        
        # Field mapping from various potential names to standard field names
        field_mapping = {
            # Name fields
            'name': ['nom', 'name', 'contact_name', 'nom_contact', 'contact_nom', 'prénom', 'prenom', 'firstname', 'first_name', 'nom_prénom', 'nom_prenom'],
            # Email fields
            'email': ['email', 'courriel', 'mail', 'email_contact', 'contact_email', 'adresse_email', 'adresse_mail', 'e-mail', 'e_mail', 'courrier_electronique', 'email_address'],
            # Phone fields
            'phone': ['telephone', 'phone', 'tel', 'telephone_contact', 'mobile', 'contact_telephone', 'téléphone', 'tél', 'portable', 'phone_number', 'numéro_téléphone', 'numero_telephone', 'cellphone', 'mobile_phone'],
            # Company fields
            'company': ['entreprise', 'company', 'société', 'organization', 'nom_entreprise', 'organization_name', 'societe', 'nom_de_la_société', 'nom_de_la_societe', 'organisation', 'business', 'etablissement', 'école', 'ecole', 'nom_établissement', 'nom_etablissement', 'institution'],
            # Position fields
            'position': ['fonction', 'position', 'titre', 'title', 'titre_contact', 'poste', 'job_title', 'role', 'rôle', 'job', 'métier', 'metier', 'responsabilité', 'responsabilite', 'profession'],
            # Website fields (will go into additional_data)
            'website': ['site_web', 'website', 'site', 'url', 'web', 'site_internet', 'web_site', 'home_page', 'url_site', 'adresse_site'],
            # LinkedIn fields (will go into additional_data)
            'linkedin': ['linkedin', 'linkedin_url', 'contact_linkedin', 'linkedin_profile', 'url_linkedin', 'lien_linkedin', 'profil_linkedin', 'compte_linkedin'],
        }
        
        # Initialize fields with empty values
        field_values = {
            'name': 'Unknown',
            'email': None,
            'phone': None,
            'company': None,
            'position': None,
        }
        
        # Extract values based on field mapping
        for field, aliases in field_mapping.items():
            for alias in aliases:
                # Check in original lead_data first
                if alias in lead_data and lead_data[alias]:
                    field_values[field] = lead_data[alias]
                    logger.debug(f"Found {field} in original data: {lead_data[alias]}")
                    break
                # Then check in normalized data
                if alias in normalized_lead_data and normalized_lead_data[alias]:
                    field_values[field] = normalized_lead_data[alias]
                    logger.debug(f"Found {field} in normalized data: {normalized_lead_data[alias]}")
                    break
        
        # Special handling for prefixed fields like contact_email -> email
        for prefix in ['contact_', 'company_', 'entreprise_']:
            for base_field in ['name', 'email', 'phone', 'position']:
                prefixed_field = f"{prefix}{base_field}"
                if prefixed_field in normalized_lead_data and normalized_lead_data[prefixed_field] and not field_values[base_field]:
                    field_values[base_field] = normalized_lead_data[prefixed_field]
                    logger.info(f"Mapping prefixed field {prefixed_field} to {base_field}: {normalized_lead_data[prefixed_field]}")
        
        # Final check for critical fields that might be buried in the data
        # Search specifically for email-like values
        if not field_values['email']:
            # Try to find any key that might contain an email
            for key, value in normalized_lead_data.items():
                if isinstance(value, str) and '@' in value and '.' in value and len(value) > 5:
                    if key not in ['description', 'site_web', 'website']:  # Exclude non-email fields
                        logger.info(f"Found potential email in field '{key}': {value}")
                        field_values['email'] = value
                        break
        
        # Search specifically for phone-like values if still missing
        if not field_values['phone']:
            # Try to find any key that might contain a phone number
            for key, value in normalized_lead_data.items():
                if isinstance(value, str) and any(char.isdigit() for char in value):
                    # Simple pattern check for phone numbers (at least 8 digits in the string)
                    digit_count = sum(1 for char in value if char.isdigit())
                    if digit_count >= 8 and key not in ['description', 'site_web', 'website']:
                        logger.info(f"Found potential phone number in field '{key}': {value}")
                        field_values['phone'] = value
                        break
        
        # Add specific checks for M2i Formation case and similar patterns
        if company_name and company_name.lower() == "m2i formation" and not field_values['email']:
            if 'contact_email' in normalized_lead_data:
                field_values['email'] = normalized_lead_data['contact_email']
                logger.info(f"Special case for M2i Formation: setting email to {field_values['email']}")
            elif any('contact' in key and '@' in str(value) for key, value in normalized_lead_data.items()):
                # Find first contact-related field with @ sign
                for key, value in normalized_lead_data.items():
                    if 'contact' in key and '@' in str(value):
                        field_values['email'] = value
                        logger.info(f"Found email in contact field '{key}': {value}")
                        break
        
        logger.debug(f"Extracted field values after prefix processing: {field_values}")
        
        # Additional data for the JSON field
        additional_data = {}
        
        # Include any other fields from lead_data that aren't standard fields
        for key, value in lead_data.items():
            if key not in [item for sublist in field_mapping.values() for item in sublist]:
                additional_data[key] = value
        
        logger.debug(f"Additional data: {additional_data}")
        
        # Check for missing required fields based on structure schema
        is_complete = True
        missing_fields = []
        required_fields = []
        
        if structure_schema:
            logger.debug(f"Validating against structure schema: {structure_schema}")
            for field in structure_schema:
                field_name = field.get("name")
                is_required = field.get("required", False)
                
                if is_required:
                    required_fields.append(field_name)
                    # Check if this field is missing in lead_data
                    field_found = False
                    
                    # Normalize the field name from the structure schema
                    normalized_field_name = field_name.replace(' ', '_').lower() if isinstance(field_name, str) else field_name
                    
                    # Try exact match with both original and normalized field names
                    if field_name in normalized_lead_data and normalized_lead_data[field_name]:
                        field_found = True
                        logger.debug(f"Required field '{field_name}' found with exact match")
                    elif normalized_field_name in normalized_lead_data and normalized_lead_data[normalized_field_name]:
                        field_found = True
                        logger.debug(f"Required field '{field_name}' found with normalized name '{normalized_field_name}'")
                    else:
                        # Check for aliases if it's a standard field
                        for std_field, aliases in field_mapping.items():
                            if field_name in aliases or normalized_field_name in aliases:
                                if field_values[std_field]:
                                    field_found = True
                                    logger.debug(f"Required field '{field_name}' matched through alias to '{std_field}'")
                                    break
                        
                        # Check for fuzzy matches in field names
                        if not field_found:
                            for key in normalized_lead_data.keys():
                                # If the key contains the field name or vice versa
                                if (isinstance(key, str) and isinstance(field_name, str) and 
                                    (field_name.lower() in key.lower() or key.lower() in field_name.lower())):
                                    if normalized_lead_data[key]:
                                        field_found = True
                                        logger.debug(f"Required field '{field_name}' found through fuzzy match with '{key}'")
                                    break
                    
                    if not field_found:
                        is_complete = False
                        missing_fields.append(field_name)
                        logger.debug(f"Required field '{field_name}' is missing")
        
        logger.info(f"Lead completeness: {is_complete}, Missing fields: {missing_fields}")
        
        # If email is a required field and it's missing, stop lead creation
        if 'email' in required_fields or 'contact_email' in required_fields:
            if not field_values['email']:
                logger.warning(f"❌ Cannot create lead for company {company_name}: Email is required but missing")
                # Update task statistics even though we're not creating a lead
                try:
                    task = scraping_result.task
                    task.incomplete_leads = getattr(task, 'incomplete_leads', 0) + 1
                    task.save(update_fields=['incomplete_leads'])
                    logger.info(f"Incremented incomplete_leads count for task {task.id}")
                    
                    # Update user profile statistics
                    if hasattr(job.user, 'profile'):
                        profile = job.user.profile
                        profile.incomplete_leads = getattr(profile, 'incomplete_leads', 0) + 1
                        profile.save(update_fields=['incomplete_leads'])
                        logger.info(f"Incremented incomplete_leads count for user {job.user.id}")
                    
                    # Log this as invalid lead
                    from .models import ScrapingLog
                    ScrapingLog.objects.create(
                        task=task,
                        log_type='warning',
                        message=f"Lead creation skipped for {company_name}: required email field missing",
                        details={"missing_fields": missing_fields, "lead_data": normalized_lead_data}
                    )
                except Exception as e:
                    logger.warning(f"Could not update task statistics: {str(e)}")
                return None
        
        # Create the Lead object
        logger.info(f"Attempting to create Lead in database for user {job.user.id}, company: {company_name}")
        try:
            from core.models import Lead, UserProfile
            
            # Check user's quota before creating the lead
            try:
                # Get user profile
                profile = None
                if hasattr(job.user, 'profile'):
                    profile = job.user.profile
                    
                    # Check if quota needs to be reset (new day)
                    profile.reset_daily_leads()
                    
                    # Check if user can create more leads (unless unlimited)
                    if not profile.unlimited_leads and profile.leads_used >= profile.leads_quota:
                        logger.warning(f"❌ Rate limit reached for user {job.user.id}: {profile.leads_used}/{profile.leads_quota} leads used")
                        
                        # Update task statistics if possible
                        try:
                            task = scraping_result.task
                            # Ensure attribute exists with getattr and default
                            task.rate_limited_leads = getattr(task, 'rate_limited_leads', 0) + 1
                            task.save(update_fields=['rate_limited_leads'])
                            logger.info(f"Incremented rate_limited_leads count for task {task.id} to {task.rate_limited_leads}")
                            
                            # Update user profile statistics
                            if hasattr(job.user, 'profile'):
                                profile = job.user.profile
                                # Ensure attribute exists with getattr and default
                                profile.rate_limited_leads = getattr(profile, 'rate_limited_leads', 0) + 1
                                profile.save(update_fields=['rate_limited_leads'])
                                logger.info(f"Incremented rate_limited_leads count for user {job.user.id} to {profile.rate_limited_leads}")
                            
                            # Log this as a rate limit issue
                            from .models import ScrapingLog
                            ScrapingLog.objects.create(
                                task=task,
                                log_type='warning',
                                message=f"Lead creation skipped for {company_name}: User quota reached ({profile.leads_used}/{profile.leads_quota})",
                                details={"rate_limit": True, "company": company_name}
                            )
                            
                            # CRITICAL: Stop the task if rate limit is reached
                            logger.warning(f"❌ Rate limit reached for user {job.user.id}. Stopping task {task.id}.")
                            task.status = 'completed'
                            task.current_step = "Task stopped: User rate limit reached"
                            task.completion_time = timezone.now()
                            task.save(update_fields=['status', 'current_step', 'completion_time'])
                            
                            # Also update the job status
                            job.status = 'completed'
                            job.save(update_fields=['status'])
                            
                            # Create log entry for task termination
                            ScrapingLog.objects.create(
                                task=task,
                                log_type='warning',
                                message=f"Task {task.id} automatically stopped: User reached lead quota ({profile.leads_used}/{profile.leads_quota})",
                                details={"rate_limit": True, "auto_stop": True}
                            )
                            
                        except Exception as stats_error:
                            logger.error(f"❌ Could not update task statistics for rate limit: {str(stats_error)}", exc_info=True)
                        
                        return None
                        
                    logger.info(f"✅ User quota check passed: {profile.leads_used}/{profile.leads_quota} leads used")
                else:
                    logger.warning(f"⚠️ No profile found for user {job.user.id}, skipping quota check")
            except Exception as quota_error:
                logger.error(f"❌ Error checking user quota: {str(quota_error)}")
            
            # If we reach here, either the user has quota available or we couldn't check it
            
            # For custom fields with spaces, make sure the data field uses normalized keys
            combined_data = {**normalized_lead_data, **additional_data}
            
            # DEBUG: Log the exact parameters being used
            lead_params = {
                "scraping_result": scraping_result,
                "user": job.user,
                "name": field_values['name'],
                "email": field_values['email'],
                "phone": field_values['phone'],
                "company": company_name,  # Use the determined company name
                "position": field_values['position'],
                "status": 'not_contacted',
                "source": f"Scraped from {job.structure.name if job.structure else 'Unknown'}",
                "source_url": scraping_result.source_url,
                "data": combined_data,
                "is_complete": is_complete,
                "missing_fields": missing_fields
            }
            
            # Ensure we're not passing None to fields that don't accept nulls
            if lead_params["company"] is None:
                lead_params["company"] = "Unknown Company"
            
            if lead_params["name"] is None or lead_params["name"] == "Unknown":
                # Try to use the company name as a fallback
                lead_params["name"] = company_name if company_name else "Unknown Contact"
            
            # Final check for email and phone fields
            if not lead_params["email"] and 'contact_email' in normalized_lead_data:
                lead_params["email"] = normalized_lead_data['contact_email']
                logger.info(f"Setting email from contact_email: {lead_params['email']}")
            
            if not lead_params["phone"] and 'contact_telephone' in normalized_lead_data:
                lead_params["phone"] = normalized_lead_data['contact_telephone']
                logger.info(f"Setting phone from contact_telephone: {lead_params['phone']}")
            
            # Log specific values for critical fields
            logger.info(f"Lead creation critical fields: company={lead_params['company']}, name={lead_params['name']}, email={lead_params['email']}, phone={lead_params['phone']}")
            
            # Check if email is still missing but we're proceeding anyway
            if not lead_params["email"]:
                logger.warning(f"⚠️ Creating lead without email for company {company_name}")
            
            logger.debug(f"Lead creation parameters: {json.dumps({k: str(v) for k, v in lead_params.items() if k != 'data'})}")
            logger.debug(f"Lead data field keys: {list(combined_data.keys())}")
            
            # Create the Lead with our parameters
            lead = Lead.objects.create(**lead_params)
            
            completion_status = "complete" if is_complete else f"incomplete (missing: {', '.join(missing_fields)})"
            logger.info(f"✅ Successfully created lead {lead.id} for user {job.user.id} from scraping result {scraping_result.id} - {completion_status}")
            
            # Update user profile - increment leads_used
            if profile and not profile.unlimited_leads:
                profile.leads_used += 1
                profile.save(update_fields=['leads_used', 'last_lead_reset'])
                logger.info(f"✅ Updated user profile: {profile.leads_used}/{profile.leads_quota} leads used")
            
            # Update structure usage statistics
            structure = job.structure
            if structure:
                try:
                    # Reset daily leads if needed (new day)
                    structure.reset_daily_leads()
                    
                    # Increment the leads extracted today
                    structure.leads_extracted_today += 1
                    structure.total_leads_extracted += 1
                    structure.last_extraction_date = timezone.now().date()
                    structure.save(update_fields=['leads_extracted_today', 'total_leads_extracted', 'last_extraction_date'])
                    
                    # Calculate and log percentage completion
                    completion_percentage = structure.get_completion_percentage()
                    logger.info(f"✅ Updated structure usage: {structure.leads_extracted_today}/{structure.leads_target_per_day} leads extracted today ({completion_percentage}%)")
                except Exception as structure_error:
                    logger.error(f"❌ Error updating structure statistics: {str(structure_error)}")
            
            # Update task statistics
            try:
                task = scraping_result.task
                task.leads_found += 1
                if is_complete:
                    task.unique_leads += 1
                task.save(update_fields=['leads_found', 'unique_leads'])
                logger.debug(f"Updated task {task.id} lead counts: leads_found={task.leads_found}, unique_leads={task.unique_leads}")
            except Exception as task_e:
                logger.warning(f"Could not update lead count for task: {str(task_e)}")
            
            return lead
        except Exception as db_error:
            logger.error(f"❌ Database error creating lead: {str(db_error)}", exc_info=True)
            
            # Check for common database issues
            if "already exists" in str(db_error).lower():
                logger.error("Appears to be a duplicate key issue - another lead with same unique constraint exists")
            if "null value in column" in str(db_error).lower():
                logger.error("Appears to be a NOT NULL constraint violation - missing required field")
            if "foreign key constraint" in str(db_error).lower():
                logger.error("Appears to be a foreign key constraint issue - referenced object doesn't exist")
                
            raise
        
    except Exception as e:
        logger.error(f"❌ Error creating lead from scraping result {scraping_result.id}: {str(e)}", exc_info=True)
        return None

def scrape_site(site, task, structure):
    """Scrape a specific site using appropriate strategy"""
    try:
        # Determine the appropriate scraping strategy
        strategy = structure.scraping_strategy
        
        if strategy == 'web_scraping':
            # Use web scraping strategy from your existing code
            logger.info(f"Using web scraping strategy for {site.url}")
            
            # Init Selenium for browser-based scraping
            try:
                from utils.simple_scraper import init_selenium, fetch_page_content, close_selenium
                init_selenium()
                
                # Fetch the page content
                raw_html = fetch_page_content(site.url)
                
                if not raw_html or raw_html.strip() == "":
                    logger.warning(f"Empty HTML content received from {site.url}. Skipping this page.")
                    close_selenium()
                    return False
                
                # Format the extracted HTML
                from utils.html_formatter import format_extracted_html
                extracted_text = format_extracted_html(raw_html, site.url)
                
                # Analyze the HTML with GPT/Mistral
                from utils.openai_api import analyze_html_with_gpt
                from core.utils.ai_utils import AIManager
                
                # Create a structure for analysis based on the structure schema
                # Start with a base site info
                json_structure = {
                    "site_info": {
                        "name": site.domain,
                        "url": site.url
                    },
                    "contacts": [],
                    "meta_data": {
                        "priority_links": [],
                        "explored_links": [site.url]
                    }
                }
                
                # Define the objective - customize based on structure entity type
                if structure.entity_type == 'mairie':
                    objective = "Récupérer les contacts et les appels d'offre liés aux services de cette organisation"
                elif structure.entity_type == 'entreprise' or structure.entity_type == 'b2b_lead':
                    objective = "Récupérer les informations de contact et de l'entreprise selon la structure demandée"
                else:
                    objective = "Récupérer les données selon la structure fournie"
                
                logger.info(f"Analyse de la page HTML avec objectif: {objective}")
                logger.debug(f"Structure d'extraction: {structure.structure}")
                
                # Check if we should use OpenAI or Mistral for analysis
                use_mistral = True
                try:
                    # Import the AIManager to check if it's available
                    ai_manager = AIManager()
                except ImportError:
                    use_mistral = False
                    logger.warning("AIManager not available, falling back to OpenAI for HTML analysis")
                
                # Log which engine we're using
                logger.info(f"Using {'Mistral' if use_mistral else 'OpenAI'} for HTML content analysis")
                
                # Analyze the HTML using the appropriate engine
                if use_mistral:
                    # Use Mistral for analysis, explicitly passing the structure schema
                    gpt_analysis = ai_manager.analyze_html_content(
                        extracted_text, 
                        objective, 
                        json_structure, 
                        structure_schema=structure.structure
                    )
                else:
                    # Use OpenAI as fallback
                    gpt_analysis = analyze_html_with_gpt(
                        extracted_text, 
                        objective, 
                        json_structure, 
                        structure_schema=structure.structure
                    )
                
                if not gpt_analysis or not isinstance(gpt_analysis, dict):
                    logger.warning(f"No valid data extracted from {site.url}, skipping.")
                    close_selenium()
                    return False
                
                # Log the analysis result for debugging
                logger.debug(f"Résultat de l'analyse HTML: {json.dumps(gpt_analysis, indent=2)}")
                
                # CRITICAL FIX: If 'nom' field exists but no company fields, map 'nom' to 'nom_entreprise'
                if 'nom' in gpt_analysis and gpt_analysis['nom'] and not any(field in gpt_analysis for field in ['nom_entreprise', 'company', 'entreprise']):
                    gpt_analysis['nom_entreprise'] = gpt_analysis['nom']
                    logger.info(f"Early mapping: Using 'nom' as company name: {gpt_analysis['nom']}")
                
                # Process the AI analysis results
                leads_processed = False
                
                # Check if industry/sector field is missing but required
                if structure.structure and "secteur_activite" in [field.get('name') for field in structure.structure if field.get('required', True)]:
                    if 'secteur_activite' in gpt_analysis and not gpt_analysis['secteur_activite']:
                        # The sector field exists but is empty, try a dedicated analysis to find it
                        logger.warning("Missing sector field detected, attempting targeted extraction...")
                        
                        try:
                            # Create a specialized prompt for industry detection
                            company_name = gpt_analysis.get('nom_entreprise', gpt_analysis.get('company', site.domain))
                            company_desc = gpt_analysis.get('description', '')
                            
                            # Get the industry analysis
                            industry_messages = [
                                {"role": "system", "content": "You are an expert in business analysis and industry classification."},
                                {"role": "user", "content": f"""
Analyze this HTML content and determine the industry sector for this company:

COMPANY NAME: {company_name}
COMPANY DESCRIPTION: {company_desc}

HTML CONTENT:
{extracted_text[:8000]}

I need ONLY the industry or business sector. Return ONLY a JSON object like this:
{{"secteur_activite": "Technology"}}

Use specific industry categories like Technology, Healthcare, Manufacturing, Financial Services, 
Education, Media, Retail, etc. Make your best determination based on the content.
If you're unsure but can make an educated guess, add "Probable: " prefix.
"""}
                            ]
                            
                            # Get the industry analysis
                            industry_result = ai_manager.send_mistral_request(industry_messages, model="mistral-large-latest")
                            
                            # If successful, update the original analysis
                            if isinstance(industry_result, dict) and 'secteur_activite' in industry_result and industry_result['secteur_activite']:
                                gpt_analysis['secteur_activite'] = industry_result['secteur_activite']
                                logger.info(f"Successfully extracted industry sector: {industry_result['secteur_activite']}")
                            elif isinstance(industry_result, str):
                                # Try to extract JSON from string if needed
                                # re and json modules are already imported at the top of the file
                                
                                # Try to find JSON pattern in the response
                                json_match = re.search(r'\{.*?"secteur_activite".*?:.*?".*?".*?\}', industry_result)
                                if json_match:
                                    try:
                                        extracted_json = json.loads(json_match.group(0))
                                        if 'secteur_activite' in extracted_json and extracted_json['secteur_activite']:
                                            gpt_analysis['secteur_activite'] = extracted_json['secteur_activite']
                                            logger.info(f"Extracted industry from text response: {extracted_json['secteur_activite']}")
                                    except:
                                        logger.warning("Failed to parse extracted industry JSON")
                        except Exception as e:
                            logger.warning(f"Error during targeted industry extraction: {str(e)}")
                
                # Check if the result has expected custom structure fields (from the structure schema)
                # This is specifically for the format returned in custom structure extraction
                has_custom_structure_fields = False
                required_fields_present = 0
                if structure.structure:
                    required_fields_total = 0
                    for field in structure.structure:
                        field_name = field.get('name')
                        is_required = field.get('required', False)
                        if is_required:
                            required_fields_total += 1
                            if field_name in gpt_analysis:
                                required_fields_present += 1
                    
                    # Check if we have at least 1 required field to consider this a valid extraction
                    if required_fields_present > 0:
                        has_custom_structure_fields = True
                        logger.info(f"Custom structure detected: {required_fields_present}/{required_fields_total} required fields present")
                        
                        # If 'nom' is present in the structure and data but 'nom_entreprise' is not,
                        # automatically map 'nom' to 'nom_entreprise' for company name recognition
                        if 'nom' in gpt_analysis and gpt_analysis['nom'] and 'nom_entreprise' not in gpt_analysis:
                            gpt_analysis['nom_entreprise'] = gpt_analysis['nom']
                            logger.info(f"Custom structure: Mapping 'nom' to 'nom_entreprise': {gpt_analysis['nom']}")
                
                # Check for company name as a key indicator
                company_name = gpt_analysis.get('nom_entreprise', gpt_analysis.get('company', None))
                if company_name:
                    logger.info(f"Company name found in extraction: {company_name}")
                
                # Handle different result structures
                if "contacts" in gpt_analysis:
                    # Standard contacts array structure
                    logger.info(f"Processing {len(gpt_analysis.get('contacts', []))} contacts from extraction")
                    for contact_data in gpt_analysis.get("contacts", []):
                        if is_valid_contact(contact_data, structure.structure):
                            # Create a new ScrapingResult for each contact
                            scraping_result = ScrapingResult.objects.create(
                                task=task,
                                lead_data=contact_data,
                                source_url=site.url
                            )
                            task.leads_found += 1
                            task.unique_leads += 1
                            task.save()
                            
                            # Log the found contact
                            ScrapingLog.objects.create(
                                task=task,
                                log_type='info',
                                message=f"Contact trouvé: {contact_data.get('nom', contact_data.get('name', 'Sans nom'))}",
                                details=contact_data
                            )
                            
                            # Create a lead from the scraping result
                            lead = create_lead_from_result(scraping_result, task.job)
                            
                            if lead:
                                ScrapingLog.objects.create(
                                    task=task,
                                    log_type='info',
                                    message=f"Created lead: {lead.name} (ID: {lead.id})",
                                    details={"lead_id": lead.id}
                                )
                        else:
                            logger.info(f"Contact rejeté: Validation échouée: {contact_data}")
                    
                    leads_processed = True
                
                # Process as a custom structure result - this is the format your logs show
                if (has_custom_structure_fields or ('nom_entreprise' in gpt_analysis)) and not leads_processed:
                    # Custom structure format - treat as a single contact/result
                    logger.info(f"Processing as custom structure with fields: {list(gpt_analysis.keys())}")
                    
                    # Enhanced logging for company name identification
                    logger.info(f"Company name detection - nom exists: {'nom' in gpt_analysis}, value: {gpt_analysis.get('nom', 'N/A')}")
                    logger.info(f"Company name detection - nom_entreprise exists: {'nom_entreprise' in gpt_analysis}, value: {gpt_analysis.get('nom_entreprise', 'N/A')}")
                    logger.info(f"Company name detection - company exists: {'company' in gpt_analysis}, value: {gpt_analysis.get('company', 'N/A')}")
                    
                    # If company name is present, we can create a lead
                    company_name = gpt_analysis.get('nom_entreprise', gpt_analysis.get('company', None))
                    
                    # Special case: If 'nom' exists but no company name found, use 'nom' as company name
                    if not company_name and 'nom' in gpt_analysis and gpt_analysis['nom']:
                        company_name = gpt_analysis['nom']
                        gpt_analysis['nom_entreprise'] = company_name  # Set it in the data for future processing
                        logger.info(f"Using 'nom' field as company name: {company_name}")
                    
                    if company_name:
                        # Always perform validation but create lead anyway with missing fields tracked
                        is_valid = is_valid_contact(gpt_analysis, structure.structure)
                        validation_result = "valid" if is_valid else "has validation issues but will be created with missing fields tracked"
                        logger.info(f"Custom structure validation result: {validation_result}")
                        
                        # Create a new ScrapingResult
                        try:
                            logger.info(f"Creating scraping result for company: {company_name}")
                            scraping_result = ScrapingResult.objects.create(
                                task=task,
                                lead_data=gpt_analysis,
                                source_url=site.url
                            )
                            logger.info(f"Scraping result created with ID: {scraping_result.id}")
                            
                            task.leads_found += 1
                            task.unique_leads += 1
                            task.save()
                            
                            # Create a lead from the result
                            logger.info(f"Creating lead from scraping result: {scraping_result.id}")
                            lead = create_lead_from_result(scraping_result, task.job)
                            
                            if lead:
                                logger.info(f"✅ Successfully created lead: {lead.name} (ID: {lead.id})")
                                ScrapingLog.objects.create(
                                    task=task,
                                    log_type='info',
                                    message=f"Created lead: {lead.name} (ID: {lead.id})",
                                    details={"lead_id": lead.id}
                                )
                            else:
                                logger.warning(f"❌ Lead creation failed for company: {company_name}")
                        except Exception as e:
                            logger.error(f"❌ Error creating lead from custom structure: {str(e)}", exc_info=True)
                    else:
                        logger.warning(f"Custom structure data rejected: No company name found. Data: {gpt_analysis}")
                    
                    leads_processed = True
                
                if not leads_processed:
                    logger.warning(f"No leads processed from extracted data: {json.dumps(gpt_analysis, indent=2)}")
                
                # Save extracted tenders
                if "tenders" in gpt_analysis:
                    for tender_data in gpt_analysis.get("tenders", []):
                        if tender_data.get("titre"):
                            # Create a new ScrapingResult for each tender
                            ScrapingResult.objects.create(
                                task=task,
                                lead_data=tender_data,
                                source_url=site.url
                            )
                            task.leads_found += 1
                            task.unique_leads += 1
                            task.save()
                            
                            # Log the found tender
                            ScrapingLog.objects.create(
                                task=task,
                                log_type='info',
                                message=f"Appel d'offre trouvé: {tender_data.get('titre', 'Sans titre')}",
                                details=tender_data
                            )
                
                close_selenium()
                return True
                
            except ImportError as e:
                logger.error(f"Required scraping modules not available: {str(e)}")
                return False
            except Exception as e:
                logger.error(f"Error during web scraping of {site.url}: {str(e)}")
                return False
                
        elif strategy == 'linkedin_scraping':
            # LinkedIn scraping logic would go here
            logger.info(f"LinkedIn scraping not yet implemented for {site.url}")
            return False
            
        elif strategy == 'api_scraping':
            # API scraping logic would go here
            logger.info(f"API scraping not yet implemented for {site.url}")
            return False
            
        else:
            # Default scraping method (simplified)
            logger.info(f"Using default scraping strategy for {site.url}")
            
            # Simulate finding some leads
            num_leads = 3
            for _ in range(num_leads):
                # Create a sample lead
                scraping_result = ScrapingResult.objects.create(
                    task=task,
                    lead_data={
                        'name': f'Sample Lead from {site.domain}',
                        'email': f'sample@{site.domain}',
                        'phone': '1234567890'
                    },
                    source_url=site.url
                )
                task.leads_found += 1
                task.unique_leads += 1
                task.save()
                
                # Create a lead from the scraping result
                create_lead_from_result(scraping_result, task.job)
            
            return True

    except Exception as e:
        logger.error(f"Error scraping site {site.url}: {str(e)}", exc_info=True)
        site.set_rate_limit(minutes=60)  # Rate limit on error
        return False

def is_valid_contact(contact, structure_schema=None):
    """
    Validates if a contact meets the requirements based on the structure schema.
    
    Args:
        contact (dict): The contact data
        structure_schema (list, optional): Schema defining what fields are required
        
    Returns:
        bool: True if contact is valid, False otherwise
    """
    logger.debug(f"Validating contact: {contact}")
    
    if not contact:
        logger.warning("Contact rejected: empty contact data")
        return False
    
    # CRITICAL: Map 'nom' to company name if needed before validation
    if 'nom' in contact and contact['nom'] and 'nom_entreprise' not in contact:
        contact['nom_entreprise'] = contact['nom']
        logger.info(f"Validation: Mapping 'nom' to 'nom_entreprise' for validation: {contact['nom']}")
        
    # If no structure schema provided, use generic validation
    if not structure_schema:
        logger.debug("No structure schema provided, using generic validation")
        
        # Generic name check
        nom = contact.get("nom", contact.get("name", "")).strip()
        if not nom:
            logger.warning(f"Contact rejected: Empty name. Details: {contact}")
            return False

        if nom.lower() in ["nom du contact", "inconnu", "unknown"]:
            logger.warning(f"Contact rejected: Generic or unknown name ({nom}). Details: {contact}")
            return False
        
        # Check if contact has at least one valid contact method
        email = contact.get("email", contact.get("courriel", contact.get("mail", ""))).strip()
        telephone = contact.get("telephone", contact.get("phone", contact.get("tel", ""))).strip()
        fonction = contact.get("fonction", contact.get("position", contact.get("titre", contact.get("title", "")))).strip()
        
        logger.debug(f"Generic validation - Name: '{nom}', Email: '{email}', Phone: '{telephone}', Position: '{fonction}'")
        
        # The contact needs at least one method to be contacted
        if not (email or telephone or fonction):
            logger.warning(f"Contact rejected: No valid contact method (function, email, phone all absent). Details: {contact}")
            return False
            
        logger.info(f"Contact validated successfully with generic validation. Name: '{nom}'")
        return True
    
    # Log the structure schema being used for validation
    logger.debug(f"Validating contact against structure schema with {len(structure_schema)} fields: {[field.get('name') for field in structure_schema]}")
    logger.debug(f"Contact data has fields: {list(contact.keys())}")
    
    # Validate against structure schema
    missing_fields = []
    found_fields = []
    company_level_fields = ['secteur_activite', 'nom_entreprise', 'entreprise', 'company', 
                           'site_web', 'description', 'taille_entreprise', 'industry']
    
    # Store required company fields and required contact fields separately
    missing_company_fields = []
    missing_contact_fields = []
    
    # Check each required field in the schema
    for field in structure_schema:
        field_name = field.get("name")
        is_required = field.get("required", False)
        
        if not is_required:
            logger.debug(f"Field '{field_name}' is not required, skipping validation")
            continue
            
        # Try field name directly
        field_value = contact.get(field_name)
        
        # If not found directly, try to map standard fields (name, email, etc.)
        if (field_value is None or (isinstance(field_value, str) and field_value.strip() == "")) and is_required:
            logger.debug(f"Required field '{field_name}' not found directly, looking for alternatives")
            
            # Check if this might be a standard field with a different name
            field_type = field.get("type", "").lower()
            alternative_value = None
            
            # Try to find alternative fields based on common naming patterns
            if field_name.endswith("_contact") or field_name in ["nom", "name"]:
                # Name field
                alternative_value = contact.get("nom") or contact.get("name")
                if alternative_value:
                    logger.debug(f"Found alternative value for '{field_name}': '{alternative_value}' (name field)")
            elif field_name in ["email", "courriel", "mail", "email_contact"]:
                # Email field
                alternative_value = contact.get("email") or contact.get("courriel") or contact.get("mail")
                if alternative_value:
                    logger.debug(f"Found alternative value for '{field_name}': '{alternative_value}' (email field)")
            elif field_name in ["telephone", "phone", "tel", "telephone_contact"]:
                # Phone field
                alternative_value = contact.get("telephone") or contact.get("phone") or contact.get("tel")
                if alternative_value:
                    logger.debug(f"Found alternative value for '{field_name}': '{alternative_value}' (phone field)")
            elif field_name in ["fonction", "position", "titre", "title", "titre_contact"]:
                # Position field
                alternative_value = contact.get("fonction") or contact.get("position") or contact.get("titre") or contact.get("title")
                if alternative_value:
                    logger.debug(f"Found alternative value for '{field_name}': '{alternative_value}' (position field)")
            elif field_name in ["entreprise", "company", "societe", "organization", "nom_entreprise"]:
                # Company field
                alternative_value = contact.get("entreprise") or contact.get("company") or contact.get("societe") or contact.get("organization") or contact.get("nom_entreprise")
                if alternative_value:
                    logger.debug(f"Found alternative value for '{field_name}': '{alternative_value}' (company field)")
            elif field_name in ["secteur_activite", "industry", "sector"]:
                # Industry field
                alternative_value = contact.get("secteur_activite") or contact.get("industry") or contact.get("sector")
                if alternative_value:
                    logger.debug(f"Found alternative value for '{field_name}': '{alternative_value}' (industry field)")
                
            # If an alternative was found, use it
            if alternative_value:
                field_value = alternative_value
        
        # Validate the field
        if is_required:
            if field_value is None or (isinstance(field_value, str) and field_value.strip() == ""):
                missing_fields.append(field_name)
                logger.debug(f"Required field '{field_name}' is missing")
                
                # Categorize the missing field
                if field_name in company_level_fields:
                    missing_company_fields.append(field_name)
                else:
                    missing_contact_fields.append(field_name)
            else:
                found_fields.append(field_name)
                logger.debug(f"Required field '{field_name}' found with value: '{field_value}'")
    
    # For company-level data, we're more lenient
    # If we're missing only company-level fields but have the main identifiers, we still accept it
    
    # Check if nom_entreprise or company is present (basic required company identifier)
    company_identifier = contact.get("nom_entreprise") or contact.get("company")
    
    # If we have company identifiers but only missing some company details, we still accept it
    if company_identifier and missing_fields and all(field in company_level_fields for field in missing_fields):
        logger.info(f"Contact accepted with missing company fields: {', '.join(missing_company_fields)}. These will be marked as incomplete in the lead.")
        return True
    
    # If there are missing required fields, reject the contact
    if missing_fields:
        logger.warning(f"Contact rejected: Missing required fields: {', '.join(missing_fields)}. Found fields: {', '.join(found_fields)}. Details: {contact}")
        return False
    
    logger.info(f"Contact validated successfully against schema. Found all required fields: {', '.join(found_fields)}")
    return True

@shared_task(base=LoggingTask, bind=True)
@track_scraping_activity('scraping')
def test_celery_connection(self):
    """Simple task to test Celery connection"""
    hostname = socket.gethostname()
    return {
        "status": "success",
        "message": f"Connection successful from {hostname}",
        "timestamp": timezone.now().isoformat()
    }

@shared_task
def check_pending_tasks():
    """
    Vérifier régulièrement les tâches de scraping en attente et les démarrer
    """
    try:
        from .models import ScrapingTask, ScrapingLog
        
        logger.info("SCRAPER: Vérification des tâches en attente...")
        
        pending_tasks = ScrapingTask.objects.filter(
            status='pending'
        ).select_related('job').order_by('-id')[:5]  # Limiter à 5 tâches à la fois
        
        count = pending_tasks.count()
        logger.info(f"SCRAPER: {count} tâches en attente trouvées")

        for task in pending_tasks:
            logger.info(f"SCRAPER: Démarrage de la tâche en attente ID: {task.id} (Job: {task.job.name})")
            
            # Mettre à jour le statut de la tâche
            task.status = 'initializing'
            task.current_step = "Tâche en cours d'initialisation..."
            task.save()
            
            # Lancer la tâche SYNCHRONOUSLY pour le débogage
            logger.info(f"DEBUG: Appel direct (synchrone) de run_scraping_task pour la tâche {task.id}")
            try:
                run_scraping_task(task.id) # Appel direct
                logger.info(f"SCRAPER: Tâche {task.id} exécutée directement (synchrone).")
            except Exception as sync_run_error:
                 logger.error(f"SCRAPER ERROR: Erreur lors de l'exécution synchrone de run_scraping_task pour {task.id}: {sync_run_error}", exc_info=True)
                 # Attempt to mark task as failed
                 try:
                     task.status = ScrapingTask.Status.FAILED
                     task.error_message = f"Failed during synchronous run: {sync_run_error}"
                     task.save(update_fields=['status', 'error_message', 'updated_at'])
                 except Exception as fail_save_error:
                     logger.error(f"SCRAPER ERROR: Impossible de marquer la tâche {task.id} comme échouée après erreur synchrone: {fail_save_error}")

            # Commented out asynchronous Celery call and related logging/updates
            # result = run_scraping_task.delay(task.id)
            # task.celery_task_id = result.id
            # task.save(update_fields=['celery_task_id'])
            # logger.info(f"SCRAPER: Tâche {task.id} lancée avec Celery task ID: {result.id}")
            
            # Mettre à jour le statut du job (peut être redondant si run_scraping_task le fait déjà)
            # job = task.job
            # job.status = 'running' # Status should be set by run_scraping_task completion/failure
            # job.save(update_fields=['status'])
            
    except Exception as e:
        logger.error(f"SCRAPER ERROR: Erreur majeure dans check_pending_tasks: {str(e)}", exc_info=True)

# Tâche de test simple pour vérifier que Celery fonctionne
@shared_task
def debug_test(message):
    """Simple task to test if Celery is working correctly"""
    logger.debug(f"DEBUG TEST: Starting debug test with message: {message}")
    
    try:
        # Log test message
        logger.info(f"DEBUG TEST: Message reçu: {message}")
        
        # Simuler du travail
        time.sleep(2)
        
        # Log de fin
        logger.debug(f"DEBUG TEST: Test completed successfully")
        return {"status": "success", "message": f"Test completed: {message}"}
    except Exception as e:
        logger.error(f"DEBUG TEST: Error in debug_test: {str(e)}")
        raise 

def start_scraping_task(task_id):
    """Starts the Celery task for scraping if conditions are met."""
    from .models import ScrapingTask  # Import here to avoid circular imports
    from django.conf import settings

    try:
        task = ScrapingTask.objects.get(pk=task_id)
        if task.status == ScrapingTask.Status.PENDING:
            task.status = ScrapingTask.Status.QUEUED
            task.save(update_fields=['status', 'updated_at'])
            logger.info(f"SCRAPER: Démarrage de la tâche en attente ID: {task.id} (Job: {task.job.name})")

            # Change from asynchronous (delay) to synchronous call for debugging
            logger.info(f"DEBUG: Appel direct de run_scraping_task pour la tâche {task.id}")
            # celery_task = run_scraping_task.delay(task.id) # Original Celery call (commented out)
            run_scraping_task(task.id) # Direct synchronous call

            # Logging after direct call completes
            logger.info(f"SCRAPER: Tâche {task.id} exécutée directement (synchrone).")
            # task.celery_task_id = celery_task.id # No longer applicable with direct call
            # task.save(update_fields=['celery_task_id', 'updated_at'])
            # logger.info(f"SCRAPER: Tâche {task.id} lancée avec Celery task ID: {celery_task.id}") # Original logging (commented out)

        else:
            logger.warning(f"SCRAPER: Tentative de démarrage de la tâche {task.id} qui n'est pas en attente (Statut: {task.status}).")
    except ScrapingTask.DoesNotExist:
        logger.error(f"SCRAPER: Tâche avec ID {task_id} non trouvée pour le démarrage.")
    except Exception as e:
        logger.error(f"SCRAPER: Erreur lors du démarrage de la tâche {task_id}: {e}", exc_info=True)
        # Optionally, try to mark the task as failed here if appropriate
        try:
            task = ScrapingTask.objects.get(pk=task_id)
            task.status = ScrapingTask.Status.FAILED
            task.error_message = f"Failed during startup: {e}"
            task.save(update_fields=['status', 'error_message', 'updated_at'])
        except ScrapingTask.DoesNotExist:
            pass # Already logged above
        except Exception as inner_e:
            logger.error(f"SCRAPER: Erreur supplémentaire lors de la tentative de marquer la tâche {task_id} comme échouée: {inner_e}") 

class ScrapingWorker:
    # ... existing code ...

    def _run_scraping_task(self, task):
        """Run the actual scraping process"""
        try:
            job = task.job
            structure = job.structure
            user = job.user
            profile = user.profile

            # Initialize scraping
            task.status = 'crawling'
            task.current_step = "Exploration des sources de données"
            task.save()

            # Get or create scraped sites for this structure
            scraped_sites = ScrapedSite.objects.filter(structure=structure)
            
            # Main scraping loop
            while task.status == 'crawling':
                # Check if we've reached the daily quota
                if not profile.unlimited_leads and profile.leads_used >= profile.leads_quota:
                    task.status = 'completed'
                    task.current_step = "Quota de leads atteint"
                    task.completion_time = timezone.now()
                    task.save()
                    
                    ScrapingLog.objects.create(
                        task=task,
                        log_type='warning',
                        message=f"Tâche interrompue: quota de leads atteint ({profile.leads_quota})"
                    )
                    break

                # Check if we have too many rate-limited or incomplete leads
                rate_limited_leads = getattr(task, 'rate_limited_leads', 0) or 0
                incomplete_leads = getattr(task, 'incomplete_leads', 0) or 0
                unique_leads = task.unique_leads or 0
                
                # If we have 10 rate-limited leads or 20 incomplete leads, or if rate limited leads are more than unique leads
                if rate_limited_leads >= 10 or incomplete_leads >= 20 or (unique_leads > 0 and rate_limited_leads >= unique_leads):
                    task.status = 'completed'
                    task.current_step = "Arrêt automatique: trop de leads limités ou incomplets"
                    task.completion_time = timezone.now()
                    task.save()
                    
                    ScrapingLog.objects.create(
                        task=task,
                        log_type='warning',
                        message=f"Tâche interrompue: {rate_limited_leads} leads limités, {incomplete_leads} leads incomplets, {unique_leads} leads uniques",
                        details={"rate_limited_leads": rate_limited_leads, "incomplete_leads": incomplete_leads, "unique_leads": unique_leads}
                    )
                    logger.info(f"Task {task.id} automatically stopped due to excessive rate-limited or incomplete leads")
                    break

                # Find next site to scrape
                site = self._get_next_site_to_scrape(scraped_sites, structure)
                if not site:
                    task.status = 'completed'
                    task.current_step = "Aucun site disponible"
                    task.completion_time = timezone.now()
                    task.save()
                    break

                # Scrape the site
                success = self._scrape_site(site, task)
                
                # Update site statistics
                site.update_scraping_stats(
                    success=success,
                    error=task.error_message if not success else None
                )

                # Update task progress
                task.pages_explored += 1
                task.save()

                # Check if we've found enough leads
                if task.unique_leads >= job.leads_allocated:
                    task.status = 'completed'
                    task.current_step = "Nombre de leads atteint"
                    task.completion_time = timezone.now()
                    task.save()
                    break

                # Small delay between sites
                time.sleep(2)  # was timezone.sleep(2)

            # Update job status
            job.leads_found = task.unique_leads
            job.status = 'completed' if task.status == 'completed' else 'failed'
            job.save()

        except Exception as e:
            logger.error(f"Error in scraping task {task.id}: {str(e)}", exc_info=True)
            task.status = 'failed'
            task.error_message = str(e)
            task.completion_time = timezone.now()
            task.save()
            
            ScrapingLog.objects.create(
                task=task,
                log_type='error',
                message=f"Erreur lors du scraping: {str(e)}"
            )