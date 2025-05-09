from django.utils import timezone
from django.db.models import Q
from django.conf import settings
import logging
import threading
from datetime import timedelta
from urllib.parse import urlparse
import time  # Add this import if not already present

from core.models import ScrapingJob, ScrapingStructure
from .models import ScrapingTask, ScrapingLog, ScrapingResult, TaskQueue, ScrapedSite

logger = logging.getLogger(__name__)

class ScrapingWorker:
    """
    Service class to handle automatic scraping tasks
    """
    def __init__(self):
        self.active_tasks = {}
        self.worker_thread = None
        self.is_running = False

    def start(self):
        """Start the worker thread"""
        if self.is_running:
            return

        self.is_running = True
        self.worker_thread = threading.Thread(target=self._run_worker)
        self.worker_thread.daemon = True
        self.worker_thread.start()
        logger.info("Scraping worker started")

    def stop(self):
        """Stop the worker thread"""
        self.is_running = False
        if self.worker_thread:
            self.worker_thread.join()
        logger.info("Scraping worker stopped")

    def _run_worker(self):
        """Main worker loop"""
        while self.is_running:
            try:
                self._process_queue()
                self._check_active_tasks()
                self._cleanup_old_tasks()
                time.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Error in worker loop: {str(e)}", exc_info=True)
                time.sleep(300)  # Wait 5 minutes on error

    def _process_queue(self):
        """Process queued tasks"""
        # Get all unprocessed queue entries
        queue_entries = TaskQueue.objects.filter(
            is_processed=False,
            scheduled_time__lte=timezone.now()
        ).select_related('job', 'job__user', 'job__structure')

        for entry in queue_entries:
            try:
                # Check user's quota and permissions
                user = entry.job.user
                profile = user.profile
                
                if not profile.can_use_advanced_scraping:
                    logger.warning(f"User {user.email} does not have advanced scraping permission")
                    entry.is_processed = True
                    entry.save()
                    continue

                # Check daily quota
                if not profile.unlimited_leads:
                    profile.reset_daily_leads()
                    if not profile.can_access_leads:
                        logger.warning(f"User {user.email} has reached their daily leads quota")
                        entry.is_processed = True
                        entry.save()
                        continue

                # Create and start new task
                self._start_task(entry.job)
                entry.is_processed = True
                entry.save()

            except Exception as e:
                logger.error(f"Error processing queue entry {entry.id}: {str(e)}", exc_info=True)
                entry.is_processed = True
                entry.save()

    def _check_active_tasks(self):
        """Check status of active tasks and handle completion"""
        for task_id, task in list(self.active_tasks.items()):
            try:
                # Refresh task from database
                task.refresh_from_db()
                
                if task.status in ['completed', 'failed']:
                    # Task is done, remove from active tasks
                    del self.active_tasks[task_id]
                    continue

                # Check if task has been running too long
                if task.duration > 3600:  # 1 hour max
                    task.status = 'failed'
                    task.error_message = "Task exceeded maximum duration"
                    task.completion_time = timezone.now()
                    task.save()
                    
                    ScrapingLog.objects.create(
                        task=task,
                        log_type='error',
                        message="Task terminated: exceeded maximum duration"
                    )
                    
                    del self.active_tasks[task_id]

            except Exception as e:
                logger.error(f"Error checking task {task_id}: {str(e)}", exc_info=True)
                del self.active_tasks[task_id]

    def _cleanup_old_tasks(self):
        """Clean up old completed tasks"""
        try:
            # Delete tasks older than 7 days
            old_date = timezone.now() - timedelta(days=7)
            ScrapingTask.objects.filter(
                status__in=['completed', 'failed'],
                completion_time__lt=old_date
            ).delete()
        except Exception as e:
            logger.error(f"Error cleaning up old tasks: {str(e)}", exc_info=True)

    def _start_task(self, job):
        """Start a new scraping task"""
        try:
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
                message=f"Tâche de scraping initialisée pour '{job.name}'"
            )

            # Start task in background
            thread = threading.Thread(
                target=self._run_scraping_task,
                args=(task,)
            )
            thread.daemon = True
            thread.start()

            # Store task reference
            self.active_tasks[task.id] = task

        except Exception as e:
            logger.error(f"Error starting task for job {job.id}: {str(e)}", exc_info=True)

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
                time.sleep(2)

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

    def _get_next_site_to_scrape(self, scraped_sites, structure):
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

    def _scrape_site(self, site, task):
        """Scrape a specific site"""
        try:
            # This is where you would implement your actual scraping logic
            # For now, we'll just simulate it
            time.sleep(5)  # Simulate scraping time
            
            # Simulate finding some leads
            num_leads = 3
            for _ in range(num_leads):
                # Create a sample lead
                ScrapingResult.objects.create(
                    task=task,
                    lead_data={
                        'name': 'Sample Lead',
                        'email': 'sample@example.com',
                        'phone': '1234567890'
                    },
                    source_url=site.url
                )
                task.leads_found += 1
                task.unique_leads += 1
                task.save()

            return True

        except Exception as e:
            logger.error(f"Error scraping site {site.url}: {str(e)}", exc_info=True)
            site.set_rate_limit(minutes=60)  # Rate limit on error
            return False

# Create a singleton instance
scraping_worker = ScrapingWorker() 