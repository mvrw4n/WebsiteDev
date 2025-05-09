import logging
from django.utils import timezone

logger = logging.getLogger(__name__)

def get_task_for_job(job):
    """
    Get the task associated with a job, checking both core and scraping models
    """
    try:
        # First try to get from the core app
        from core.models import ScrapingTask as CoreScrapingTask
        core_tasks = job.core_tasks.all()
        if core_tasks.exists():
            core_task = core_tasks.latest('id')
            logger.info(f"Found core task for job {job.id}: {core_task.id}")
            return {
                'source': 'core',
                'task': core_task,
                'to_dict': core_task.to_dict()
            }
    except Exception as e:
        logger.error(f"Error getting core task for job {job.id}: {str(e)}")
    
    try:
        # Then try to get from the scraping app
        from scraping.models import ScrapingTask as ScrapingScrapingTask
        scraping_tasks = job.scraping_tasks.all()
        if scraping_tasks.exists():
            scraping_task = scraping_tasks.latest('start_time')
            logger.info(f"Found scraping task for job {job.id}: {scraping_task.id}")
            # Convert scraping task to dict format matching core task
            task_dict = {
                'id': scraping_task.celery_task_id or str(scraping_task.id),
                'status': scraping_task.status,
                'current_step': scraping_task.current_step or 'Processing',
                'pages_explored': scraping_task.pages_explored,
                'leads_found': scraping_task.leads_found,
                'unique_leads': scraping_task.unique_leads,
                'start_time': scraping_task.start_time.isoformat() if scraping_task.start_time else None,
                'last_activity': scraping_task.last_activity.isoformat() if scraping_task.last_activity else None,
                'completion_time': scraping_task.completion_time.isoformat() if scraping_task.completion_time else None,
                'duration': int(scraping_task.duration),
                'error_message': scraping_task.error_message or ''
            }
            return {
                'source': 'scraping',
                'task': scraping_task,
                'to_dict': task_dict
            }
    except Exception as e:
        logger.error(f"Error getting scraping task for job {job.id}: {str(e)}")
    
    # If we reach here, no task was found
    return None

def get_job_details(job_id):
    """
    Get comprehensive details for a job including its task
    """
    try:
        from core.models import ScrapingJob
        job = ScrapingJob.objects.get(id=job_id)
        
        # Get the job data
        job_data = job.to_dict()
        
        # Now try to get the task
        task_data = get_task_for_job(job)
        if task_data:
            job_data['task'] = task_data['to_dict']
            job_data['task_source'] = task_data['source']
        else:
            # No task found, create placeholder
            job_data['task'] = {
                'id': None,
                'status': 'unknown',
                'current_step': 'No task information available',
                'pages_explored': 0,
                'leads_found': 0,
                'unique_leads': 0,
                'start_time': job.created_at.isoformat(),
                'last_activity': job.updated_at.isoformat(),
                'duration': 0
            }
            job_data['task_source'] = 'placeholder'
        
        return {
            'success': True,
            'job': job_data
        }
        
    except ScrapingJob.DoesNotExist:
        return {
            'success': False,
            'error': 'Job not found'
        }
    except Exception as e:
        logger.error(f"Error getting job details: {str(e)}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }

def get_active_jobs():
    """
    Get all active jobs with their task information
    """
    try:
        from core.models import ScrapingJob
        active_jobs = ScrapingJob.objects.filter(
            status__in=['initializing', 'running', 'paused']
        ).order_by('-created_at')
        
        jobs_data = []
        for job in active_jobs:
            try:
                job_dict = job.to_dict()
                
                # Add task information
                task_data = get_task_for_job(job)
                if task_data:
                    job_dict['task'] = task_data['to_dict']
                    job_dict['task_source'] = task_data['source']
                else:
                    # Add default task info
                    job_dict['task'] = {
                        'id': None,
                        'status': 'unknown',
                        'current_step': 'Waiting to start...',
                        'pages_explored': 0,
                        'leads_found': 0,
                        'unique_leads': 0,
                        'duration': 0
                    }
                    job_dict['task_source'] = 'placeholder'
                
                jobs_data.append(job_dict)
            except Exception as e:
                logger.error(f"Error processing job {job.id}: {str(e)}")
        
        return {
            'success': True,
            'active_jobs': jobs_data
        }
    except Exception as e:
        logger.error(f"Error getting active jobs: {str(e)}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }

def get_history_jobs():
    """
    Get completed or historical jobs with their task information
    """
    try:
        from core.models import ScrapingJob
        history_jobs = ScrapingJob.objects.filter(
            status__in=['completed', 'failed', 'stopped']
        ).order_by('-created_at')[:20]
        
        jobs_data = []
        for job in history_jobs:
            try:
                job_dict = job.to_dict()
                
                # Add task information
                task_data = get_task_for_job(job)
                if task_data:
                    job_dict['task'] = task_data['to_dict']
                    job_dict['task_source'] = task_data['source']
                else:
                    # Create default task based on job status
                    status_map = {
                        'completed': 'completed',
                        'failed': 'failed',
                        'stopped': 'revoked'
                    }
                    
                    job_dict['task'] = {
                        'id': None,
                        'status': status_map.get(job.status, 'unknown'),
                        'current_step': get_status_message(job.status),
                        'pages_explored': 0,
                        'leads_found': job.leads_found or 0,
                        'unique_leads': job.leads_found or 0,
                        'duration': 0
                    }
                    job_dict['task_source'] = 'placeholder'
                
                jobs_data.append(job_dict)
            except Exception as e:
                logger.error(f"Error processing history job {job.id}: {str(e)}")
        
        return {
            'success': True,
            'history_jobs': jobs_data
        }
    except Exception as e:
        logger.error(f"Error getting history jobs: {str(e)}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }

def get_status_message(status):
    """Get a user-friendly message for job status"""
    status_messages = {
        'completed': 'Tâche terminée avec succès',
        'failed': 'Tâche échouée',
        'stopped': 'Tâche arrêtée manuellement'
    }
    return status_messages.get(status, 'Statut inconnu') 