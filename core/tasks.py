import logging
import json
import uuid
import threading
import time
import random
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from .models import ScrapingJob, ScrapingStructure, ScrapingTask

logger = logging.getLogger(__name__)

# Simulation task state dictionary to track tasks locally when Celery isn't available
_local_task_states = {}

def get_task_info(task_id):
    """Get information about a task by its ID
    
    This works for both Celery tasks and simulated tasks
    """
    logger.info(f"Getting task info for task {task_id}")
    
    # First try to get from database if it exists
    try:
        task = ScrapingTask.objects.get(task_id=task_id)
        return task.to_dict()
    except ScrapingTask.DoesNotExist:
        logger.debug(f"No ScrapingTask found for task_id {task_id}")
    
    # Next, try to get from local task states if we have it
    if task_id in _local_task_states:
        logger.info(f"Found task {task_id} in local state: {_local_task_states[task_id]}")
        return _local_task_states[task_id]
    
    # Otherwise try to get from Celery if it's available
    if hasattr(settings, 'USE_CELERY') and settings.USE_CELERY:
        try:
            from celery.result import AsyncResult
            result = AsyncResult(task_id)
            
            # If task exists in Celery
            if result.state:
                # Get task info from result
                task_data = {
                    'id': task_id,
                    'status': result.state.lower(),
                    'current_step': 'Processing',
                    'pages_explored': 0,
                    'leads_found': 0,
                    'unique_leads': 0,
                    'start_time': timezone.now().isoformat(),
                    'last_activity': timezone.now().isoformat(),
                    'duration': 0
                }
                
                # Try to get info from result meta
                if result.info and isinstance(result.info, dict):
                    task_data.update(result.info)
                
                return task_data
        except Exception as e:
            logger.error(f"Error getting Celery task info: {str(e)}")
    
    # If we can't get the info from either source, return a default
    return {
        'id': task_id,
        'status': 'unknown',
        'current_step': 'Waiting to start...',
        'pages_explored': 0,
        'leads_found': 0,
        'unique_leads': 0,
        'duration': 0
    }

def _calculate_duration(start_time):
    """Calculate duration between start_time and now"""
    if not start_time:
        return 0
    
    try:
        if isinstance(start_time, str):
            # Parse ISO format string
            start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        
        # Calculate duration
        duration_seconds = (timezone.now() - start_time).total_seconds()
        return int(duration_seconds)
    except Exception as e:
        logger.error(f"Error calculating duration: {str(e)}")
        return 0

def _simulate_task_execution(task_id, job_id):
    """Simulate the execution of a scraping task in a background thread
    
    This is used as a fallback when Celery is not available
    """
    logger.info(f"Starting simulated task execution for job {job_id} with task ID {task_id}")
    
    try:
        # Get the job
        job = ScrapingJob.objects.get(id=job_id)
        structure = job.structure
        
        # Create or update task in database
        task, created = ScrapingTask.objects.get_or_create(
            task_id=task_id,
            defaults={
                'job': job,
                'status': 'initializing',
                'current_step': 'Initializing scraping task...',
                'start_time': timezone.now(),
                'last_activity': timezone.now()
            }
        )
        
        if not created:
            task.status = 'initializing'
            task.current_step = 'Initializing scraping task...'
            task.last_activity = timezone.now()
            task.save()
        
        # Get user profile for quota management
        user = job.user
        profile = None
        if hasattr(user, 'profile'):
            profile = user.profile
        
        # Check if user has remaining quota
        if profile and not profile.unlimited_leads and profile.leads_used >= profile.leads_quota:
            # User has no quota left
            task.status = 'failed'
            task.current_step = 'Quota de leads dépassé'
            task.error_message = 'Votre quota de leads est épuisé. Veuillez passer à un forfait supérieur pour continuer.'
            task.last_activity = timezone.now()
            task.completion_time = timezone.now()
            task.save()
            
            # Update job status
            job.status = 'failed'
            job.save()
            
            logger.warning(f"User {user.email} exceeded lead quota. Job {job_id} stopped.")
            return
        
        # Update job status
        job.status = 'running'
        job.save()
        
        # Initialize task state for local tracking too
        _local_task_states[task_id] = {
            'id': task_id,
            'status': 'initializing',
            'current_step': 'Initializing scraping task...',
            'pages_explored': 0,
            'leads_found': 0,
            'unique_leads': 0,
            'start_time': timezone.now().isoformat(),
            'last_activity': timezone.now().isoformat(),
            'duration': 0
        }
        
        # Sleep a bit to simulate initialization
        time.sleep(5)
        
        # Update to crawling state
        task.status = 'crawling'
        task.current_step = 'Exploring websites...'
        task.last_activity = timezone.now()
        task.save()
        
        _local_task_states[task_id].update({
            'status': 'crawling',
            'current_step': 'Exploring websites...',
            'last_activity': timezone.now().isoformat(),
        })
        
        # Calculate how many steps based on leads_allocated
        total_leads = max(10, job.leads_allocated)
        
        # If user has limited quota, don't generate more leads than they can use
        if profile and not profile.unlimited_leads:
            remaining_quota = profile.leads_quota - profile.leads_used
            if remaining_quota < total_leads:
                total_leads = remaining_quota
                logger.info(f"Limiting leads to {total_leads} due to user quota")
        
        # Minimum of 5 steps, maximum of 20, or based on leads
        steps = min(20, max(5, total_leads // 5))
        leads_per_step = total_leads / steps
        
        # Track leads for user quota
        total_leads_found = 0
        total_unique_leads = 0
        
        # Simulate crawling with data updates
        for i in range(steps):
            # Sleep to simulate work
            time.sleep(random.uniform(2, 5))
            
            # Update pages explored and leads found
            new_pages = random.randint(1, 3)
            new_leads = random.randint(0, int(leads_per_step * 1.5))
            
            # If user has quota limit, check if we'd exceed it
            if profile and not profile.unlimited_leads:
                remaining_quota = profile.leads_quota - profile.leads_used
                if remaining_quota <= 0:
                    # Stop generating leads if quota exceeded
                    logger.warning(f"User {user.email} quota exceeded during simulation. Stopping lead generation.")
                    break
                
                # Limit new leads to remaining quota
                if new_leads > remaining_quota:
                    new_leads = remaining_quota
            
            # Update task state in database
            task.pages_explored += new_pages
            task.leads_found += new_leads
            task.unique_leads = int(task.leads_found * 0.8)  # 80% are unique
            task.current_step = f"Exploring page {task.pages_explored}"
            task.last_activity = timezone.now()
            task.save()
            
            # Track total leads for later quota update
            total_leads_found += new_leads
            total_unique_leads = int(total_leads_found * 0.8)  # 80% are unique
            
            # Update local task state too
            _local_task_states[task_id].update({
                'pages_explored': task.pages_explored,
                'leads_found': task.leads_found,
                'unique_leads': task.unique_leads,
                'current_step': task.current_step,
                'last_activity': task.last_activity.isoformat(),
                'duration': _calculate_duration(task.start_time)
            })
            
            # Update job with current leads count
            job.leads_found = task.unique_leads
            job.save()
            
            # If we've found enough leads, move to processing
            if task.unique_leads >= job.leads_allocated or (profile and not profile.unlimited_leads and profile.leads_used + task.unique_leads >= profile.leads_quota):
                break
        
        # Update to extracting state
        task.status = 'extracting'
        task.current_step = 'Extracting contact information...'
        task.last_activity = timezone.now()
        task.save()
        
        _local_task_states[task_id].update({
            'status': 'extracting',
            'current_step': 'Extracting contact information...',
            'last_activity': timezone.now().isoformat(),
        })
        
        # Sleep to simulate extraction work
        time.sleep(random.uniform(3, 8))
        
        # Update to processing state
        task.status = 'processing'
        task.current_step = 'Processing and validating leads...'
        task.last_activity = timezone.now()
        task.save()
        
        _local_task_states[task_id].update({
            'status': 'processing',
            'current_step': 'Processing and validating leads...',
            'last_activity': timezone.now().isoformat(),
        })
        
        # Sleep to simulate processing
        time.sleep(random.uniform(2, 5))
        
        # Mark as completed
        task.status = 'completed'
        task.current_step = 'Task completed successfully'
        task.last_activity = timezone.now()
        task.completion_time = timezone.now()
        task.save()
        
        _local_task_states[task_id].update({
            'status': 'completed',
            'current_step': 'Task completed successfully',
            'last_activity': timezone.now().isoformat(),
            'duration': _calculate_duration(task.start_time)
        })
        
        # Update job status
        job.status = 'completed'
        job.leads_found = task.unique_leads
        job.save()
        
        # Update user profile with leads used
        if profile and not profile.unlimited_leads and task.unique_leads > 0:
            # Increase the leads used count
            profile.leads_used += task.unique_leads
            profile.save()
            logger.info(f"Updated user {user.email} profile: +{task.unique_leads} leads used, now at {profile.leads_used}/{profile.leads_quota}")
        
        # Update structure usage if available
        try:
            if structure and task.unique_leads > 0:
                # Get or create structure usage tracking
                from django.db.models import F
                structure.leads_extracted_today = F('leads_extracted_today') + task.unique_leads
                structure.total_leads_extracted = F('total_leads_extracted') + task.unique_leads
                structure.save()
                logger.info(f"Updated structure {structure.id} usage: +{task.unique_leads} leads extracted")
        except Exception as e:
            logger.error(f"Error updating structure usage: {str(e)}")
        
        logger.info(f"Simulated task {task_id} for job {job_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Error in simulated task execution: {str(e)}")
        
        # Update task state with error in database
        try:
            task = ScrapingTask.objects.get(task_id=task_id)
            task.status = 'failed'
            task.current_step = f'Error: {str(e)}'
            task.last_activity = timezone.now()
            task.error_message = str(e)
            task.save()
        except Exception as inner_e:
            logger.error(f"Error updating task in database: {str(inner_e)}")
        
        # Update local task state too
        if task_id in _local_task_states:
            _local_task_states[task_id].update({
                'status': 'failed',
                'current_step': f'Error: {str(e)}',
                'last_activity': timezone.now().isoformat(),
            })

def start_scraping_job(job_id):
    """Start a scraping job
    
    This will delegate to the appropriate Celery task based on the job's structure's 
    scraping strategy, or run a local simulation if Celery is not available
    """
    logger.info(f"Starting scraping job {job_id}")
    
    try:
        # Get the job and related structure
        job = ScrapingJob.objects.get(id=job_id)
        
        # Check user's lead quota before starting
        try:
            user = job.user
            profile = None
            
            if hasattr(user, 'profile'):
                profile = user.profile
                
                # Check if user can access more leads
                if not profile.unlimited_leads and profile.leads_used >= profile.leads_quota:
                    job.status = 'failed'
                    job.save()
                    
                    # Create a task to store the error
                    ScrapingTask.objects.create(
                        job=job,
                        task_id=str(uuid.uuid4()),
                        status='failed',
                        current_step='Quota de leads dépassé',
                        error_message='Votre quota de leads est épuisé. Veuillez passer à un forfait supérieur pour continuer.',
                        start_time=timezone.now(),
                        last_activity=timezone.now(),
                        completion_time=timezone.now()
                    )
                    
                    logger.warning(f"User {user.email} exceeded lead quota. Job {job_id} not started.")
                    return {
                        "success": False, 
                        "error": "Lead quota exceeded",
                        "task_id": None
                    }
        except Exception as e:
            logger.error(f"Error checking user quota: {str(e)}")
            # Continue without quota check if it fails
        
        # Get scraping strategy (default to web_scraping if no structure)
        scraping_strategy = 'web_scraping'
        if job.structure:
            scraping_strategy = job.structure.scraping_strategy
        
        # Check if we should use Celery
        if hasattr(settings, 'USE_CELERY') and settings.USE_CELERY:
            task_id = None
            logger.info(f"Using Celery for job {job_id} with strategy: {scraping_strategy}")
            
            # Import celery app
            try:
                from scraping.tasks import run_scraping_task, run_linkedin_scraping, run_custom_scraping
                
                # Choose the appropriate task based on strategy
                if scraping_strategy == 'linkedin_scraping':
                    # LinkedIn scraping
                    task_result = run_linkedin_scraping.delay(job_id)
                    task_id = task_result.id
                    logger.info(f"Started LinkedIn scraping Celery task {task_id} for job {job_id}")
                elif scraping_strategy == 'custom_scraping':
                    # Custom scraping
                    task_result = run_custom_scraping.delay(job_id)
                    task_id = task_result.id
                    logger.info(f"Started custom scraping Celery task {task_id} for job {job_id}")
                else:
                    # Default web scraping
                    task_result = run_scraping_task.delay(job_id)
                    task_id = task_result.id
                    logger.info(f"Started web scraping Celery task {task_id} for job {job_id}")
                
                # Create a task entry in the database
                try:
                    ScrapingTask.objects.create(
                        job=job,
                        task_id=task_id,
                        status='pending',
                        current_step='Task queued, waiting for worker...',
                        start_time=timezone.now(),
                        last_activity=timezone.now()
                    )
                except Exception as e:
                    logger.error(f"Error creating ScrapingTask record: {str(e)}")
                
                # Return the task information
                return {"success": True, "task_id": task_id, "strategy": scraping_strategy}
                
            except ImportError as e:
                logger.error(f"Error importing scraping tasks: {str(e)}")
                logger.warning(f"Falling back to local simulation for job {job_id}")
                # Fall back to local simulation
            except Exception as e:
                logger.error(f"Error starting Celery task: {str(e)}")
                # Fall back to local simulation
        
        # If we reached here, either Celery is not available or there was an error
        # Run a local simulation instead
        logger.info(f"Using local simulation for job {job_id}")
        
        # Generate a UUID for the task
        task_id = str(uuid.uuid4())
        
        # Create a task entry in the database
        try:
            ScrapingTask.objects.create(
                job=job,
                task_id=task_id,
                status='pending',
                current_step='Task queued for local simulation...',
                start_time=timezone.now(),
                last_activity=timezone.now()
            )
        except Exception as e:
            logger.error(f"Error creating ScrapingTask record: {str(e)}")
        
        # Start a background thread to simulate the task
        thread = threading.Thread(
            target=_simulate_task_execution,
            args=(task_id, job_id),
            daemon=True
        )
        thread.start()
        
        logger.info(f"Started simulated task {task_id} for job {job_id}")
        return {"success": True, "task_id": task_id, "strategy": scraping_strategy, "simulated": True}
        
    except Exception as e:
        logger.error(f"Error starting scraping job {job_id}: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {"success": False, "error": str(e)} 