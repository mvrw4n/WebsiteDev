from django.contrib import admin
from django.urls import reverse, path
from django.utils.html import format_html
from django.utils import timezone
from django.template.response import TemplateResponse
from django.contrib import messages
from django.http import HttpResponseRedirect, JsonResponse
from django.contrib.admin.sites import site
from .models import ScrapingTask, ScrapingLog, ScrapingResult, TaskQueue, ScrapedSite
from core.models import ScrapingStructure
import json
import sys
from django.db import models
import logging
import socket
import time
import os

# Configure logger
logger = logging.getLogger(__name__)

# Try to import TaskResult if django_celery_results is installed
try:
    from django_celery_results.models import TaskResult
    HAS_CELERY_RESULTS = True
except ImportError:
    HAS_CELERY_RESULTS = False

# Register models with admin
@admin.register(ScrapingTask)
class ScrapingTaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'job_link', 'status', 'pages_explored', 'leads_found', 'unique_leads', 
                   'start_time', 'completion_time', 'duration_display')
    list_filter = ('status', 'start_time', 'completion_time')
    search_fields = ('job__name', 'status', 'current_step')
    readonly_fields = ('start_time', 'last_activity', 'completion_time', 'duration_display')
    
    def duration_display(self, obj):
        if obj.duration:
            minutes, seconds = divmod(int(obj.duration), 60)
            hours, minutes = divmod(minutes, 60)
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return "N/A"
    duration_display.short_description = "Duration"
    
    def job_link(self, obj):
        url = reverse("admin:core_scrapingjob_change", args=[obj.job.id])
        return format_html('<a href="{}">{}</a>', url, obj.job.name)
    job_link.short_description = "Job"

@admin.register(ScrapingLog)
class ScrapingLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'task_link', 'timestamp', 'log_type', 'short_message')
    list_filter = ('log_type', 'timestamp')
    search_fields = ('message',)
    
    def task_link(self, obj):
        url = reverse("admin:scraping_scrapingtask_change", args=[obj.task.id])
        return format_html('<a href="{}">{}</a>', url, obj.task.id)
    task_link.short_description = "Task"
    
    def short_message(self, obj):
        return obj.message[:100] + "..." if len(obj.message) > 100 else obj.message
    short_message.short_description = "Message"

@admin.register(ScrapingResult)
class ScrapingResultAdmin(admin.ModelAdmin):
    list_display = ('id', 'task_link', 'result_type', 'is_duplicate', 'created_at')
    list_filter = ('is_duplicate', 'created_at')
    search_fields = ('lead_data',)
    
    def task_link(self, obj):
        url = reverse("admin:scraping_scrapingtask_change", args=[obj.task.id])
        return format_html('<a href="{}">{}</a>', url, obj.task.id)
    task_link.short_description = "Task"
    
    def result_type(self, obj):
        if 'nom' in obj.lead_data or 'name' in obj.lead_data:
            return "Contact"
        elif 'titre' in obj.lead_data or 'title' in obj.lead_data:
            return "Tender"
        return "Unknown"
    result_type.short_description = "Type"

@admin.register(TaskQueue)
class TaskQueueAdmin(admin.ModelAdmin):
    list_display = ('id', 'job_link', 'priority', 'scheduled_time', 'is_processed', 'created_at')
    list_filter = ('priority', 'is_processed', 'created_at')
    actions = ['process_selected_queue_entries']
    
    def job_link(self, obj):
        url = reverse("admin:core_scrapingjob_change", args=[obj.job.id])
        return format_html('<a href="{}">{}</a>', url, obj.job.name)
    job_link.short_description = "Job"
    
    def process_selected_queue_entries(self, request, queryset):
        from scraping.tasks import start_job
        for queue_entry in queryset.filter(is_processed=False):
            start_job.delay(queue_entry.job.id)
            queue_entry.is_processed = True
            queue_entry.save()
        self.message_user(request, f"Started processing {queryset.count()} queue entries")
    process_selected_queue_entries.short_description = "Process selected queue entries"

@admin.register(ScrapedSite)
class ScrapedSiteAdmin(admin.ModelAdmin):
    list_display = ('id', 'domain', 'structure_link', 'scraping_count', 'success_rate', 
                   'last_scraped', 'is_rate_limited', 'can_scrape')
    list_filter = ('domain', 'created_at')
    search_fields = ('url', 'domain')
    readonly_fields = ('scraping_count', 'success_rate', 'last_scraped', 'rate_limit_until')
    actions = ['clear_rate_limits']
    
    def structure_link(self, obj):
        url = reverse("admin:core_scrapingstructure_change", args=[obj.structure.id])
        return format_html('<a href="{}">{}</a>', url, obj.structure.name)
    structure_link.short_description = "Structure"
    
    def is_rate_limited(self, obj):
        return obj.is_rate_limited
    is_rate_limited.boolean = True
    is_rate_limited.short_description = "Rate Limited"
    
    def can_scrape(self, obj):
        return obj.can_scrape
    can_scrape.boolean = True
    can_scrape.short_description = "Can Scrape"
    
    def clear_rate_limits(self, request, queryset):
        queryset.update(rate_limit_until=None)
        self.message_user(request, f"Cleared rate limits for {queryset.count()} sites")
    clear_rate_limits.short_description = "Clear rate limits"

# Register Celery Task Results in admin
if HAS_CELERY_RESULTS:
    # Check if TaskResult is already registered
    from django.apps import apps
    if apps.is_installed('django_celery_results'):
        from django.contrib.admin.sites import site
        
        # Only if the model is registered, unregister it
        try:
            site.unregister(TaskResult)
            
            # Then register with our custom admin
            class TaskResultAdmin(admin.ModelAdmin):
                list_display = ('task_id', 'task_name', 'status', 'date_done', 'result')
                list_filter = ('status', 'date_done')
                search_fields = ('task_id', 'task_name')
                readonly_fields = ('task_id', 'task_name', 'status', 'date_done', 'result')
                
            admin.site.register(TaskResult, TaskResultAdmin)
        except:
            # If it's not registered or there's another error, just skip
            pass

# Custom admin view for Scraping Control Panel
class ScrapingControlPanelView:
    def __init__(self):
        self.admin_site = admin.site
    
    def get_urls(self):
        urls = [
            path('scraping/control-panel/', self.admin_site.admin_view(self.control_panel_view), name='scraping_control_panel'),
            path('scraping/toggle-task/<int:task_id>/', self.admin_site.admin_view(self.toggle_periodic_task), name='toggle_periodic_task'),
            path('scraping/start-manual-scrape/<int:structure_id>/', self.admin_site.admin_view(self.start_manual_scrape), name='start_manual_scrape'),
            path('scraping/purge-tasks/', self.admin_site.admin_view(self.purge_tasks), name='purge_scraping_tasks'),
            path('scraping/toggle-automatic-scraping/', self.admin_site.admin_view(self.toggle_automatic_scraping), name='toggle_automatic_scraping'),
            path('scraping/test-celery-connection/', self.admin_site.admin_view(self.test_celery_connection), name='test_celery_connection'),
            # New endpoints for enhanced monitoring
            path('scraping/active-tasks/', self.admin_site.admin_view(self.get_active_tasks), name='get_active_tasks'),
            path('scraping/task-history/', self.admin_site.admin_view(self.get_task_history), name='get_task_history'),
            path('scraping/worker-logs/', self.admin_site.admin_view(self.get_worker_logs), name='get_worker_logs'),
            path('scraping/worker-stats/<str:worker_name>/', self.admin_site.admin_view(self.get_worker_stats), name='get_worker_stats'),
            path('scraping/shutdown-worker/<str:worker_name>/', self.admin_site.admin_view(self.shutdown_worker), name='shutdown_worker'),
            path('scraping/revoke-task/<str:task_id>/', self.admin_site.admin_view(self.revoke_task), name='revoke_task'),
            # Add scraping logs endpoint
            path('scraping/scraping-logs/', self.admin_site.admin_view(self.get_scraping_logs), name='get_scraping_logs'),
        ]
        return urls

    def control_panel_view(self, request):
        """Display the scraping control panel"""
        # Import within function to avoid circular import
        from .tasks import AUTOMATIC_SCRAPING_ENABLED
        
        # Get all periodic tasks related to scraping
        try:
            from django_celery_beat.models import PeriodicTask
            periodic_tasks = PeriodicTask.objects.filter(
                name__in=['check-user-agents', 'cleanup-old-tasks']
            ).order_by('name')
        except ImportError:
            periodic_tasks = []
        
        # Get all scraping structures
        structures = ScrapingStructure.objects.all().order_by('name')
        
        # Add site count to each structure
        for structure in structures:
            structure.site_count = ScrapedSite.objects.filter(structure=structure).count()
            structure.structure_type = structure.get_entity_type_display()
        
        # Get active scraping tasks
        active_tasks = ScrapingTask.objects.filter(
            status__in=['initializing', 'crawling', 'extracting', 'processing']
        ).order_by('-start_time')
        
        # Add progress to active tasks
        for task in active_tasks:
            task.progress = task.progress_percentage
        
        # Get recent completed tasks
        recent_tasks = ScrapingTask.objects.filter(
            status__in=['completed', 'failed']
        ).order_by('-completion_time')[:10]
        
        # Add duration display to recent tasks
        for task in recent_tasks:
            if hasattr(task, 'duration'):
                minutes, seconds = divmod(int(task.duration), 60)
                hours, minutes = divmod(minutes, 60)
                task.duration_display = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                task.duration_display = "N/A"
        
        # Count tasks by status
        task_stats = {
            'total': ScrapingTask.objects.count(),
            'active': active_tasks.count(),
            'completed': ScrapingTask.objects.filter(status='completed').count(),
            'failed': ScrapingTask.objects.filter(status='failed').count()
        }
        
        # Get Celery worker status
        worker_status = self.get_worker_status()
        
        context = {
            'title': 'Scraping Control Panel',
            'periodic_tasks': periodic_tasks,
            'structures': structures,
            'active_tasks': active_tasks,
            'recent_tasks': recent_tasks,
            'task_stats': task_stats,
            'worker_status': worker_status,
            'automatic_scraping_enabled': AUTOMATIC_SCRAPING_ENABLED,
            'has_permission': True,
            'site_header': admin.site.site_header,
        }
        
        return TemplateResponse(request, 'admin/scraping/control_panel.html', context)
    
    def toggle_automatic_scraping(self, request):
        """Toggle the automatic scraping flag"""
        if request.method == 'POST':
            # Import the module where the global variable is defined
            import scraping.tasks as tasks_module
            
            # Toggle the flag
            tasks_module.AUTOMATIC_SCRAPING_ENABLED = not tasks_module.AUTOMATIC_SCRAPING_ENABLED
            
            # Also disable/enable all periodic tasks
            try:
                from django_celery_beat.models import PeriodicTask
                PeriodicTask.objects.filter(
                    name__in=['check-user-agents', 'cleanup-old-tasks']
                ).update(enabled=tasks_module.AUTOMATIC_SCRAPING_ENABLED)
            except ImportError:
                pass
            
            return JsonResponse({
                'success': True,
                'enabled': tasks_module.AUTOMATIC_SCRAPING_ENABLED,
                'message': 'Automatic scraping has been ' + ('enabled' if tasks_module.AUTOMATIC_SCRAPING_ENABLED else 'disabled')
            })
        
        return JsonResponse({
            'success': False,
            'message': 'Invalid request method'
        })
    
    def toggle_periodic_task(self, request, task_id):
        try:
            from django_celery_beat.models import PeriodicTask
            task = PeriodicTask.objects.get(id=task_id)
            task.enabled = not task.enabled
            task.save()
            
            status = "enabled" if task.enabled else "disabled"
            messages.success(request, f"Task '{task.name}' was {status}")
        except (PeriodicTask.DoesNotExist, ImportError):
            messages.error(request, "Task not found or Celery Beat not installed")
        
        return HttpResponseRedirect(reverse('admin:scraping_control_panel'))
    
    def start_manual_scrape(self, request, structure_id):
        from scraping.tasks import start_structure_scrape
        
        try:
            structure = ScrapingStructure.objects.get(id=structure_id)
            # Call the Celery task to start scraping for this structure
            task = start_structure_scrape.delay(structure_id)
            
            messages.success(request, f"Started manual scraping for '{structure.name}'. Task ID: {task.id}")
        except ScrapingStructure.DoesNotExist:
            messages.error(request, "Structure not found")
        
        return HttpResponseRedirect(reverse('admin:scraping_control_panel'))
    
    def purge_tasks(self, request):
        # Delete old completed and failed tasks
        old_date = timezone.now() - timezone.timedelta(days=7)
        count = ScrapingTask.objects.filter(
            status__in=['completed', 'failed'],
            completion_time__lt=old_date
        ).count()
        
        ScrapingTask.objects.filter(
            status__in=['completed', 'failed'],
            completion_time__lt=old_date
        ).delete()
        
        messages.success(request, f"Purged {count} old tasks")
        return HttpResponseRedirect(reverse('admin:scraping_control_panel'))
    
    def get_worker_status(self):
        """Get Celery worker status with improved detection"""
        try:
            # Import celery app directly
            from wizzydjango.celery import app
            import socket
            import time
            import os
            
            # Get Celery broker URL for diagnostics
            broker_url = app.conf.get('broker_url', 'Unknown')
            
            logger.info(f"Checking worker status with broker: {broker_url}")
            
            # First try basic ping with increased timeout
            ping_result = app.control.ping(timeout=3.0)
            
            if ping_result:
                workers = []
                
                # Handle ping_result being either a list or dictionary
                if isinstance(ping_result, dict):
                    # Old Celery versions return dict
                    for worker_name, response in ping_result.items():
                        workers.append({
                            'name': worker_name,
                            'status': 'online',
                            'tasks': {
                                'active': 0,
                                'scheduled': 0,
                                'processed': 0
                            }
                        })
                elif isinstance(ping_result, list):
                    # Newer Celery versions return list of dicts
                    for response in ping_result:
                        # Each response should be a dict with one key (worker name)
                        for worker_name, details in response.items():
                            workers.append({
                                'name': worker_name,
                                'status': 'online',
                                'tasks': {
                                    'active': 0,
                                    'scheduled': 0,
                                    'processed': 0
                                }
                            })
                
                # Try to get more detailed stats if possible
                try:
                    insp = app.control.inspect()
                    active = insp.active() or {}
                    scheduled = insp.scheduled() or {}
                    stats = insp.stats() or {}
                    
                    # Update worker stats with more details
                    for worker in workers:
                        worker_name = worker['name']
                        worker['tasks']['active'] = len(active.get(worker_name, []))
                        worker['tasks']['scheduled'] = len(scheduled.get(worker_name, []))
                        
                        # Extract worker stats
                        worker_stats = stats.get(worker_name, {})
                        worker['tasks']['processed'] = worker_stats.get('total', {}).get('total', 0)
                        
                        # Add hostname and other details
                        worker['hostname'] = worker_stats.get('hostname', 'Unknown')
                        worker['pid'] = worker_stats.get('pid', 'Unknown')
                        worker['time'] = worker_stats.get('clock', 'Unknown')
                        worker['version'] = worker_stats.get('sw_ver', 'Unknown')
                except Exception as e:
                    # We still have basic worker info from ping
                    logger.warning(f"Could not get detailed worker stats: {str(e)}")
                    pass
                    
                return {
                    'workers': workers,
                    'count': len(workers),
                    'error': None,
                    'broker': broker_url
                }
            else:
                # No ping response, but check if Redis is accessible
                broker_type = "unknown"
                if broker_url and broker_url.startswith('redis://'):
                    broker_type = "redis"
                elif broker_url and broker_url.startswith('amqp://'):
                    broker_type = "rabbitmq"
                
                # Try to connect to broker for diagnostics
                broker_check = "Not attempted"
                if broker_type == "redis":
                    try:
                        import redis
                        from urllib.parse import urlparse
                        
                        # Parse the Redis URL
                        parsed_url = urlparse(broker_url)
                        host = parsed_url.hostname or 'localhost'
                        port = parsed_url.port or 6379
                        db = int(parsed_url.path.replace('/', '') or 0)
                        password = parsed_url.password
                        
                        # Try to connect to Redis
                        redis_client = redis.Redis(host=host, port=port, db=db, 
                                                  password=password, socket_connect_timeout=3.0)
                        ping_response = redis_client.ping()
                        broker_check = f"Redis responded: {ping_response}"
                    except Exception as re:
                        broker_check = f"Redis connection error: {str(re)}"
                
                # Check process list for celery workers (not perfect but helpful)
                ps_check = "Not attempted"
                try:
                    if os.name == 'posix':  # Linux/Mac
                        import subprocess
                        ps_output = subprocess.check_output(['ps', 'aux'], text=True)
                        celery_lines = [line for line in ps_output.split('\n') if 'celery' in line and 'worker' in line]
                        ps_check = f"Found {len(celery_lines)} possible Celery worker processes"
                    elif os.name == 'nt':  # Windows
                        import subprocess
                        ps_output = subprocess.check_output(['tasklist', '/FI', 'IMAGENAME eq python.exe'], text=True)
                        celery_lines = [line for line in ps_output.split('\n') if 'python' in line]
                        ps_check = f"Found {len(celery_lines)} Python processes (may include Celery workers)"
                except Exception as pe:
                    ps_check = f"Process check error: {str(pe)}"
                
                # Check if we can connect to the local machine on common Celery ports
                port_check = "Not attempted"
                common_ports = [6379, 5672]  # Redis and RabbitMQ default ports
                open_ports = []
                try:
                    for port in common_ports:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(1)
                        result = sock.connect_ex(('127.0.0.1', port))
                        if result == 0:
                            open_ports.append(port)
                        sock.close()
                    port_check = f"Open ports: {open_ports if open_ports else 'None'}"
                except Exception as se:
                    port_check = f"Socket check error: {str(se)}"
                
                # Get Celery diagnostics
                error_msg = (
                    "No workers responded to ping. Ensure worker is running with: "
                    "celery -A wizzydjango worker -l info\n\n"
                    f"Broker URL: {broker_url}\n"
                    f"Broker check: {broker_check}\n"
                    f"Process check: {ps_check}\n"
                    f"Port check: {port_check}\n"
                )
                
                return {
                    'workers': [],
                    'count': 0,
                    'error': error_msg,
                    'broker': broker_url
                }
        except Exception as e:
            import traceback
            return {
                'workers': [],
                'count': 0,
                'error': f"{str(e)}\n{traceback.format_exc()}"
            }

    def test_celery_connection(self, request):
        """Test Celery connection by running a simple task"""
        if request.method == 'POST':
            try:
                # First, check if the Celery worker is actually running
                from wizzydjango.celery import app
                ping_result = app.control.ping(timeout=1.0)
                
                if not ping_result:
                    return JsonResponse({
                        'success': False,
                        'error': 'No Celery workers responded to ping. Make sure Celery is running.'
                    })
                
                # If we have workers, run a test task
                from scraping.tasks import test_celery_connection
                
                try:
                    # Run the test task
                    result = test_celery_connection.delay()
                    
                    # Try to get the result with a short timeout
                    try:
                        task_result = result.get(timeout=5)
                        return JsonResponse({
                            'success': True,
                            'result': task_result,
                            'message': 'Celery connection successful'
                        })
                    except Exception as e:
                        # Task was submitted but getting result failed
                        logger.warning(f"Task submitted but couldn't get result: {str(e)}")
                        return JsonResponse({
                            'success': True,
                            'message': 'Task submitted successfully, but could not get result. This might be because your Celery result backend is not configured correctly.',
                            'task_id': result.id,
                            'error_details': str(e)
                        })
                except Exception as e:
                    import traceback
                    logger.error(f"Error running test task: {str(e)}")
                    return JsonResponse({
                        'success': False,
                        'error': f"Error running test task: {str(e)}",
                        'traceback': traceback.format_exc()
                    })
            except Exception as e:
                import traceback
                logger.error(f"Error connecting to Celery: {str(e)}")
                return JsonResponse({
                    'success': False,
                    'error': f"Error connecting to Celery: {str(e)}",
                    'traceback': traceback.format_exc()
                })
        
        return JsonResponse({
            'success': False,
            'error': 'Invalid request method'
        })

    def get_active_tasks(self, request):
        """Get active tasks from Celery"""
        if request.method != 'GET':
            return JsonResponse({'success': False, 'error': 'Invalid request method'})
            
        try:
            # Import celery app
            from wizzydjango.celery import app
            
            # Get active tasks
            inspector = app.control.inspect()
            active_tasks = inspector.active() or {}
            
            # Format active tasks
            formatted_tasks = []
            for worker_name, tasks in active_tasks.items():
                for task in tasks:
                    formatted_tasks.append({
                        'id': task.get('id'),
                        'name': task.get('name'),
                        'args': task.get('args'),
                        'kwargs': task.get('kwargs'),
                        'started': task.get('time_start'),
                        'worker': worker_name
                    })
            
            return JsonResponse({
                'success': True,
                'tasks': formatted_tasks
            })
        except Exception as e:
            logger.error(f"Error getting active tasks: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': f"Error getting active tasks: {str(e)}"
            })
    
    def get_task_history(self, request):
        """Get task history from Celery Results backend"""
        if request.method != 'GET':
            return JsonResponse({'success': False, 'error': 'Invalid request method'})
            
        try:
            # Check if django_celery_results is installed
            if not HAS_CELERY_RESULTS:
                return JsonResponse({
                    'success': False,
                    'error': 'django_celery_results is not installed'
                })
            
            # Get filter parameters
            task_type = request.GET.get('task_type')
            task_status = request.GET.get('task_status')
            
            # Get tasks from the database
            from django_celery_results.models import TaskResult
            query = TaskResult.objects.all()
            
            if task_type:
                query = query.filter(task_name__contains=task_type)
            if task_status:
                query = query.filter(status=task_status)
            
            # Limit to recent tasks
            query = query.order_by('-date_done')[:50]
            
            # Format tasks
            tasks = []
            for result in query:
                try:
                    # Try to parse the result as JSON
                    if result.result:
                        try:
                            result_data = json.loads(result.result)
                        except:
                            result_data = result.result
                    else:
                        result_data = None
                    
                    tasks.append({
                        'id': result.task_id,
                        'name': result.task_name,
                        'status': result.status,
                        'created': result.date_created.strftime('%Y-%m-%d %H:%M:%S') if result.date_created else None,
                        'started': None,  # Not available in TaskResult model
                        'completed': result.date_done.strftime('%Y-%m-%d %H:%M:%S') if result.date_done else None,
                        'result': result_data,
                        'traceback': result.traceback
                    })
                except Exception as task_error:
                    # If there's an error processing a task, add error info
                    tasks.append({
                        'id': result.task_id,
                        'name': result.task_name,
                        'status': result.status,
                        'error': str(task_error)
                    })
            
            return JsonResponse({
                'success': True,
                'tasks': tasks
            })
            
        except Exception as e:
            logger.error(f"Error getting task history: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': f"Error getting task history: {str(e)}"
            })
    
    def get_worker_logs(self, request):
        """Get worker logs by reading the Celery log file"""
        if request.method != 'GET':
            return JsonResponse({'success': False, 'error': 'Invalid request method'})
            
        try:
            # Get filter parameters
            log_level = request.GET.get('log_level', 'INFO')
            
            # This is a simplified implementation - in a real app you'd want to:
            # 1. Configure Celery to write to a specific log file
            # 2. Use file rotation to manage log size
            # 3. Implement proper parsing of log levels and timestamps
            
            # Try to locate Celery log file - this is highly dependent on your setup
            import os
            from django.conf import settings
            
            # Check common locations for the log file
            log_dirs = [
                settings.BASE_DIR,
                os.path.join(settings.BASE_DIR, 'logs'),
                '/var/log/celery',
                '/var/log',
                os.path.expanduser('~')
            ]
            
            log_filenames = [
                'celery.log',
                'celery-worker.log',
                'wizzydjango-celery.log'
            ]
            
            log_content = "No Celery log file found. Configure Celery to write logs to a file."
            log_file_found = False
            
            # Try to find and read a log file
            for log_dir in log_dirs:
                for filename in log_filenames:
                    log_path = os.path.join(log_dir, filename)
                    if os.path.isfile(log_path):
                        try:
                            with open(log_path, 'r') as f:
                                # Read the last 1000 lines (or fewer if the file is smaller)
                                lines = f.readlines()[-1000:]
                                # Filter by log level
                                filtered_lines = [line for line in lines if f"{log_level}/" in line]
                                if log_level == 'ERROR':
                                    # Also include traceback lines for errors
                                    traceback_lines = [line for line in lines if "Traceback" in line]
                                    filtered_lines.extend(traceback_lines)
                                log_content = ''.join(filtered_lines)
                                log_file_found = True
                                break
                        except Exception as file_error:
                            log_content = f"Error reading log file {log_path}: {str(file_error)}"
                
                if log_file_found:
                    break
            
            # If no log file found, try to provide helpful information
            if not log_file_found:
                # Try to get logs from Celery's internal logger if possible
                try:
                    import logging
                    celery_logger = logging.getLogger('celery')
                    if celery_logger.handlers:
                        for handler in celery_logger.handlers:
                            if hasattr(handler, 'baseFilename'):
                                log_path = handler.baseFilename
                                with open(log_path, 'r') as f:
                                    lines = f.readlines()[-1000:]
                                    filtered_lines = [line for line in lines if f"{log_level}/" in line]
                                    log_content = ''.join(filtered_lines)
                                    log_file_found = True
                                    break
                except Exception as logger_error:
                    log_content = f"Error accessing Celery logger: {str(logger_error)}"
            
            # If still no logs found, suggest the user configure logging
            if not log_file_found:
                log_content += "\n\nTo configure Celery logging, add this to your settings:\n\n"
                log_content += "CELERY_WORKER_LOG_FORMAT = '[%(asctime)s: %(levelname)s/%(processName)s] %(message)s'\n"
                log_content += "CELERY_WORKER_TASK_LOG_FORMAT = '[%(asctime)s: %(levelname)s/%(processName)s] [%(task_name)s(%(task_id)s)] %(message)s'\n"
                log_content += "CELERY_WORKER_REDIRECT_STDOUTS = True\n"
                log_content += "CELERY_WORKER_REDIRECT_STDOUTS_LEVEL = 'INFO'\n\n"
                log_content += "And start Celery with the --logfile option:\n"
                log_content += "celery -A wizzydjango worker --logfile=celery.log"
            
            return JsonResponse({
                'success': True,
                'log_level': log_level,
                'log_content': log_content
            })
            
        except Exception as e:
            logger.error(f"Error getting worker logs: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': f"Error getting worker logs: {str(e)}"
            })
    
    def get_worker_stats(self, request, worker_name):
        """Get detailed stats for a worker"""
        if request.method != 'GET':
            return JsonResponse({'success': False, 'error': 'Invalid request method'})
            
        try:
            # Import celery app
            from wizzydjango.celery import app
            
            # Get inspector
            inspector = app.control.inspect([worker_name])
            
            # Collect worker stats
            stats = inspector.stats() or {}
            active = inspector.active() or {}
            scheduled = inspector.scheduled() or {}
            reserved = inspector.reserved() or {}
            revoked = inspector.revoked() or {}
            registered = inspector.registered() or {}
            
            # Format worker stats
            worker_stats = {
                'name': worker_name,
                'stats': stats.get(worker_name, {}),
                'active_tasks': active.get(worker_name, []),
                'scheduled_tasks': scheduled.get(worker_name, []),
                'reserved_tasks': reserved.get(worker_name, []),
                'revoked_tasks': revoked.get(worker_name, []),
                'registered_tasks': registered.get(worker_name, [])
            }
            
            return JsonResponse({
                'success': True,
                'worker': worker_stats
            })
            
        except Exception as e:
            logger.error(f"Error getting worker stats: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': f"Error getting worker stats: {str(e)}"
            })
    
    def shutdown_worker(self, request, worker_name):
        """Shutdown a worker"""
        if request.method != 'POST':
            return JsonResponse({'success': False, 'error': 'Invalid request method'})
            
        try:
            # Import celery app
            from wizzydjango.celery import app
            
            # Send shutdown command to the worker
            app.control.broadcast('shutdown', destination=[worker_name])
            
            return JsonResponse({
                'success': True,
                'message': f"Shutdown command sent to worker {worker_name}"
            })
            
        except Exception as e:
            logger.error(f"Error shutting down worker: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': f"Error shutting down worker: {str(e)}"
            })
    
    def revoke_task(self, request, task_id):
        """Revoke a task"""
        if request.method != 'POST':
            return JsonResponse({'success': False, 'error': 'Invalid request method'})
            
        try:
            # Import celery app
            from wizzydjango.celery import app
            
            # Revoke the task
            app.control.revoke(task_id, terminate=True)
            
            return JsonResponse({
                'success': True,
                'message': f"Task {task_id} revoked"
            })
            
        except Exception as e:
            logger.error(f"Error revoking task: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': f"Error revoking task: {str(e)}"
            })

    def get_scraping_logs(self, request):
        """Get detailed scraping logs from the database"""
        if request.method != 'GET':
            return JsonResponse({'success': False, 'error': 'Invalid request method'})
            
        try:
            # Get filter parameters
            task_id = request.GET.get('task_id')
            log_type = request.GET.get('log_type')
            
            # Get scraping logs from the database
            from .models import ScrapingLog, ScrapingTask
            
            # Start with all logs, ordered by timestamp descending
            query = ScrapingLog.objects.select_related('task', 'task__job').order_by('-timestamp')
            
            # Apply filters
            if task_id:
                query = query.filter(task_id=task_id)
            
            if log_type:
                query = query.filter(log_type=log_type)
            
            # Limit to 500 most recent logs
            query = query[:500]
            
            # Format logs
            logs = []
            for log in query:
                try:
                    # Basic log data
                    log_data = {
                        'id': log.id,
                        'task_id': log.task.id if log.task else None,
                        'log_type': log.log_type,
                        'message': log.message,
                        'timestamp': log.timestamp.strftime('%Y-%m-%d %H:%M:%S') if log.timestamp else None,
                        'details': log.details
                    }
                    
                    # Add task info if available
                    if log.task:
                        log_data['task_info'] = {
                            'id': log.task.id,
                            'status': log.task.status,
                            'job': {
                                'id': log.task.job.id if log.task.job else None,
                                'name': log.task.job.name if log.task.job else 'Unknown Job'
                            }
                        }
                    
                    logs.append(log_data)
                except Exception as log_error:
                    # If there's an error processing a log, add error info
                    logger.error(f"Error processing log {log.id}: {str(log_error)}")
                    logs.append({
                        'id': log.id,
                        'task_id': log.task.id if log.task else None,
                        'log_type': 'error',
                        'message': f"Error processing log: {str(log_error)}",
                        'timestamp': log.timestamp.strftime('%Y-%m-%d %H:%M:%S') if log.timestamp else None
                    })
            
            return JsonResponse({
                'success': True,
                'logs': logs,
                'count': len(logs)
            })
            
        except Exception as e:
            logger.error(f"Error getting scraping logs: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': f"Error getting scraping logs: {str(e)}"
            })

# Get the original get_urls method
original_get_urls = admin.site.get_urls

# Define a function to add our URLs to the original ones
def get_urls_with_scraping_panel():
    urls = [
        path('scraping/control-panel/', admin.site.admin_view(ScrapingControlPanelView().control_panel_view), name='scraping_control_panel'),
        path('scraping/toggle-task/<int:task_id>/', admin.site.admin_view(ScrapingControlPanelView().toggle_periodic_task), name='toggle_periodic_task'),
        path('scraping/start-manual-scrape/<int:structure_id>/', admin.site.admin_view(ScrapingControlPanelView().start_manual_scrape), name='start_manual_scrape'),
        path('scraping/purge-tasks/', admin.site.admin_view(ScrapingControlPanelView().purge_tasks), name='purge_scraping_tasks'),
        path('scraping/toggle-automatic-scraping/', admin.site.admin_view(ScrapingControlPanelView().toggle_automatic_scraping), name='toggle_automatic_scraping'),
        path('scraping/test-celery-connection/', admin.site.admin_view(ScrapingControlPanelView().test_celery_connection), name='test_celery_connection'),
        path('scraping/active-tasks/', admin.site.admin_view(ScrapingControlPanelView().get_active_tasks), name='get_active_tasks'),
        path('scraping/task-history/', admin.site.admin_view(ScrapingControlPanelView().get_task_history), name='get_task_history'),
        path('scraping/worker-logs/', admin.site.admin_view(ScrapingControlPanelView().get_worker_logs), name='get_worker_logs'),
        path('scraping/worker-stats/<str:worker_name>/', admin.site.admin_view(ScrapingControlPanelView().get_worker_stats), name='get_worker_stats'),
        path('scraping/shutdown-worker/<str:worker_name>/', admin.site.admin_view(ScrapingControlPanelView().shutdown_worker), name='shutdown_worker'),
        path('scraping/revoke-task/<str:task_id>/', admin.site.admin_view(ScrapingControlPanelView().revoke_task), name='revoke_task'),
        path('scraping/scraping-logs/', admin.site.admin_view(ScrapingControlPanelView().get_scraping_logs), name='get_scraping_logs'),
    ]
    return urls + original_get_urls()

# Replace the method
admin.site.get_urls = get_urls_with_scraping_panel

# Add the control panel to the admin index
admin.site.index_template = 'admin/scraping/index.html'
