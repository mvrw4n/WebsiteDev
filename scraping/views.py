from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
import logging
import json
import random
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from django.views import View
from django.conf import settings
from django.db.models import F, Q
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.core.paginator import Paginator
import socket

from core.models import ScrapingJob, ScrapingStructure
from .models import ScrapingTask, ScrapingLog, ScrapingResult, TaskQueue, CeleryWorkerActivity
from .tasks import start_structure_scrape, run_scraping_task

logger = logging.getLogger(__name__)

class ScrapingTaskDetailView(View):
    """View for getting details of a scraping task"""
    
    def get(self, request, task_id):
        try:
            task = get_object_or_404(ScrapingTask, id=task_id)
            
            # Basic information
            data = {
                'id': task.id,
                'job_id': task.job.id,
                'job_name': task.job.name,
                'status': task.status,
                'current_step': task.current_step,
                'pages_explored': task.pages_explored,
                'leads_found': task.leads_found,
                'unique_leads': task.unique_leads,
                'duplicate_leads': task.duplicate_leads,
                'start_time': task.start_time.isoformat() if task.start_time else None,
                'last_activity': task.last_activity.isoformat() if task.last_activity else None,
                'completion_time': task.completion_time.isoformat() if task.completion_time else None,
                'progress_percentage': task.progress_percentage,
                'duration': task.duration,
                'error_message': task.error_message,
            }
            
            return JsonResponse(data)
            
        except Exception as e:
            logger.error(f"Error in ScrapingTaskDetailView: {str(e)}", exc_info=True)
            return JsonResponse({
                'error': str(e)
            }, status=500)

class ScrapingTaskLogsView(View):
    """View for getting logs of a scraping task"""
    
    def get(self, request, task_id):
        try:
            task = get_object_or_404(ScrapingTask, id=task_id)
            
            # Get logs with optional pagination
            page = int(request.GET.get('page', 1))
            per_page = int(request.GET.get('per_page', 20))
            
            start = (page - 1) * per_page
            end = start + per_page
            
            logs = task.logs.all().order_by('-timestamp')[start:end]
            
            data = {
                'task_id': task.id,
                'page': page,
                'per_page': per_page,
                'total': task.logs.count(),
                'logs': [
                    {
                'id': log.id,
                'timestamp': log.timestamp.isoformat(),
                'log_type': log.log_type,
                'message': log.message,
                        'details': log.details,
                    }
                    for log in logs
                ]
            }
            
            return JsonResponse(data)
            
        except Exception as e:
            logger.error(f"Error in ScrapingTaskLogsView: {str(e)}", exc_info=True)
            return JsonResponse({
                'error': str(e)
            }, status=500)

class ScrapingTaskResultsView(View):
    """View for getting results of a scraping task"""
    
    def get(self, request, task_id):
        try:
            task = get_object_or_404(ScrapingTask, id=task_id)
            
            # Get results with optional pagination
            page = int(request.GET.get('page', 1))
            per_page = int(request.GET.get('per_page', 20))
            
            start = (page - 1) * per_page
            end = start + per_page
            
            results = task.results.all().order_by('-created_at')[start:end]
            
            data = {
                'task_id': task.id,
                'page': page,
                'per_page': per_page,
                'total': task.results.count(),
                'results': [
                    {
                'id': result.id,
                'lead_data': result.lead_data,
                'source_url': result.source_url,
                'is_duplicate': result.is_duplicate,
                        'created_at': result.created_at.isoformat(),
                    }
                    for result in results
                ]
            }
            
            return JsonResponse(data)
            
        except Exception as e:
            logger.error(f"Error in ScrapingTaskResultsView: {str(e)}", exc_info=True)
            return JsonResponse({
                'error': str(e)
            }, status=500)

class ScrapingTaskControlView(View):
    """View for controlling a scraping task (start, pause, resume, stop)"""
    
    def post(self, request, task_id=None, job_id=None):
        try:
            data = json.loads(request.body)
            action = data.get('action', '').lower()
            
            if job_id:
                # Starting a new task for a job
                if action != 'start':
                    return JsonResponse({
                        'error': 'Invalid action for job'
                    }, status=400)
                
                job = get_object_or_404(ScrapingJob, id=job_id)
                
                # Check if user has permission to start this job
                if job.user.id != request.user.id and not request.user.is_staff:
                    return JsonResponse({
                        'error': 'Permission denied'
                    }, status=403)
                
                from .tasks import start_job
                result = start_job.delay(job_id)
            
                return JsonResponse({
                    'success': True,
                    'job_id': job_id,
                    'task_id': result.id,
                    'message': f"Task started for job '{job.name}'"
                })
                
            elif task_id:
                # Controlling an existing task
                task = get_object_or_404(ScrapingTask, id=task_id)
            
                # Check if user has permission to control this task
                if task.job.user.id != request.user.id and not request.user.is_staff:
                    return JsonResponse({
                        'error': 'Permission denied'
                    }, status=403)
                
                if action == 'pause':
                    if task.status in ['initializing', 'crawling', 'extracting', 'processing']:
                        task.status = 'paused'
                        task.save()
                        ScrapingLog.objects.create(
                            task=task,
                            log_type='action',
                            message="Task paused by user"
                        )
                        return JsonResponse({
                            'success': True,
                            'message': 'Task paused'
                        })
                    else:
                        return JsonResponse({
                            'error': f"Cannot pause task with status '{task.status}'"
                        }, status=400)
                    
                elif action == 'resume':
                    if task.status == 'paused':
                        task.status = 'crawling'
                        task.save()
                        ScrapingLog.objects.create(
                            task=task,
                            log_type='action',
                            message="Task resumed by user"
                        )
                        return JsonResponse({
                            'success': True,
                            'message': 'Task resumed'
                        })
                    else:
                        return JsonResponse({
                            'error': f"Cannot resume task with status '{task.status}'"
                        }, status=400)
                    
                elif action == 'stop':
                    if task.status in ['initializing', 'crawling', 'extracting', 'processing', 'paused']:
                        task.status = 'completed'
                        task.completion_time = timezone.now()
                        task.save()
                        ScrapingLog.objects.create(
                            task=task,
                            log_type='action',
                            message="Task stopped by user"
                        )
                        # Update job status
                        task.job.status = 'completed'
                        task.job.save()
                        return JsonResponse({
                            'success': True,
                            'message': 'Task stopped'
                        })
                    else:
                        return JsonResponse({
                            'error': f"Cannot stop task with status '{task.status}'"
                        }, status=400)
                else:
                    return JsonResponse({
                        'error': f"Invalid action '{action}'"
                    }, status=400)
            else:
                return JsonResponse({
                    'error': 'Missing task_id or job_id'
                }, status=400)
            
        except Exception as e:
            logger.error(f"Error in ScrapingTaskControlView: {str(e)}", exc_info=True)
            return JsonResponse({
                'error': str(e)
            }, status=500)

class ScrapingStructureListView(APIView):
    """View for listing scraping structures"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            # Verify authentication
            if not request.user.is_authenticated:
                return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
                
            # Get structures for the user
            structures = ScrapingStructure.objects.filter(user=request.user).order_by('-created_at')
            
            # Prepare data for each structure
            structure_data = []
            for structure in structures:
                # Get statistics for the structure
                last_task = structure.tasks.order_by('-start_time').first()
                daily_current = 0
                daily_target = structure.leads_target_per_day or 10
                
                # Calculate leads extracted today
                today = timezone.now().date()
                if last_task and last_task.start_time and last_task.start_time.date() == today:
                    daily_current = last_task.leads_found or 0
                
                structure_data.append({
                    'id': structure.id,
                    'name': structure.name,
                    'entity_type': structure.entity_type,
                    'scraping_strategy': structure.scraping_strategy,
                    'structure': structure.structure,
                    'created_at': structure.created_at,
                    'daily_current': daily_current,
                    'daily_target': daily_target,
                    'leads_target_per_day': structure.leads_target_per_day,
                    'is_active': structure.is_active,
                })
            
            # Get user profile for rate limiting information
            user_profile = request.user.profile
            user_stats = {
                'leads_used': user_profile.leads_used,
                'leads_quota': user_profile.leads_quota,
                'has_rate_limit': not user_profile.unlimited_leads,
                'rate_limited_leads': getattr(user_profile, 'rate_limited_leads', 0),
                'incomplete_leads': getattr(user_profile, 'incomplete_leads', 0)
            }
            
            # Get rate limited leads count from all tasks
            rate_limited_leads = 0
            incomplete_leads = 0
            user_tasks = ScrapingTask.objects.filter(job__user=request.user)
            for task in user_tasks:
                rate_limited_leads += getattr(task, 'rate_limited_leads', 0) or 0
                incomplete_leads += getattr(task, 'incomplete_leads', 0) or 0
            
            user_stats['rate_limited_leads'] = rate_limited_leads
            user_stats['incomplete_leads'] = incomplete_leads
            
            return Response({
                'structures': structure_data,
                'user_stats': user_stats
            })
            
        except Exception as e:
            logger.error(f"Error in ScrapingStructureListView: {str(e)}", exc_info=True)
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class StartStructureScrapingView(View):
    """View for starting a scraping task for a structure from the dashboard"""
    
    def post(self, request, structure_id):
        try:
            structure = get_object_or_404(ScrapingStructure, id=structure_id)
            
            # Check if user has permission to scrape this structure
            if request.user.is_authenticated:
                if structure.user.id != request.user.id and not request.user.is_staff:
                    return JsonResponse({
                        'success': False,
                        'message': 'Permission denied'
                    }, status=403)
        
                # Start scraping for this structure
                from .tasks import start_structure_scrape
                result = start_structure_scrape.delay(structure_id)
            
                # Delay object might have a different structure than what we expect
                response_data = result.get(timeout=5) if hasattr(result, 'get') else {"success": True, "message": "Task started"}
                
                # Make sure we have a proper response
                if isinstance(response_data, dict) and "job_id" in response_data:
                    return JsonResponse(response_data)
                else:
                    return JsonResponse({
                        'success': True,
                        'task_id': str(result),
                        'message': f"Started scraping for '{structure.name}'"
                    })
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Authentication required'
                }, status=401)
                
        except Exception as e:
            logger.error(f"Error in StartStructureScrapingView: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=500)

class ActiveTasksView(View):
    """View for getting all active scraping tasks"""
    
    def get(self, request):
        try:
            # Get active tasks based on status
            active_statuses = ['initializing', 'crawling', 'extracting', 'processing', 'paused']
            
            # Check for AJAX request or API call
            is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            is_api_request = request.path.startswith('/api/')
            
            if request.user.is_staff:
                # Staff users can see all active tasks
                tasks = ScrapingTask.objects.filter(status__in=active_statuses).select_related('job').order_by('-start_time')
            elif request.user.is_authenticated:
                # Regular users can only see their own tasks
                tasks = ScrapingTask.objects.filter(
                    status__in=active_statuses,
                    job__user=request.user
                ).select_related('job').order_by('-start_time')
            elif is_ajax or is_api_request:
                # For AJAX/API requests, return empty list with 200 status
                # instead of 401 to avoid breaking frontend functionality
                return JsonResponse({
                    'success': True,
                    'count': 0,
                    'tasks': [],
                    'message': 'Not logged in - no tasks available'
                })
            else:
                # For regular page requests from unauthenticated users
                # Return 401 with a proper message
                return JsonResponse({
                    'success': False,
                    'message': 'Authentication required'
                }, status=401)
            
            # Format the task data
            tasks_data = []
            for task in tasks:
                task_data = {
                    'id': task.id,
                    'job_id': task.job.id,
                    'job_name': task.job.name,
                    'status': task.status,
                    'current_step': task.current_step,
                    'pages_explored': task.pages_explored,
                    'leads_found': task.leads_found,
                    'unique_leads': task.unique_leads,
                    'duplicate_leads': task.duplicate_leads,
                    'start_time': task.start_time.isoformat() if task.start_time else None,
                    'last_activity': task.last_activity.isoformat() if task.last_activity else None,
                    'progress_percentage': task.progress_percentage,
                    'duration': task.duration,
                }
                tasks_data.append(task_data)
                
            return JsonResponse({
                'success': True,
                'count': len(tasks_data),
                'tasks': tasks_data
            })
                
        except Exception as e:
            logger.error(f"Error in ActiveTasksView: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=500)

class WorkerActivityView(APIView):
    """View to get the current worker activity for all or a specific task"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, task_id=None, *args, **kwargs):
        try:
            if task_id:
                # Get activity for a specific task
                task = get_object_or_404(ScrapingTask, id=task_id)
                
                # Check if user owns this task
                if task.job.user != request.user and not request.user.is_staff:
                    return Response({'error': 'You do not have permission to view this task'}, 
                                   status=status.HTTP_403_FORBIDDEN)
                
                # Get workers for this specific task
                activities = CeleryWorkerActivity.objects.filter(task=task).order_by('-timestamp')
                
                # Format the activities
                activity_data = []
                for activity in activities:
                    activity_data.append({
                        'id': activity.id,
                        'worker_name': activity.worker_name,
                        'hostname': activity.hostname,
                        'activity_type': activity.activity_type,
                        'activity_display': activity.get_activity_type_display(),
                        'status': activity.status,
                        'status_display': activity.get_status_display(),
                        'current_url': activity.current_url,
                        'details': activity.details,
                        'timestamp': activity.timestamp.isoformat(),
                        'task': {
                            'id': task.id,
                            'status': task.status,
                            'status_display': task.get_status_display(),
                            'pages_explored': task.pages_explored,
                            'leads_found': task.leads_found,
                            'unique_leads': task.unique_leads,
                            'job_name': task.job.name,
                        } if task else None
                    })
                
                return Response({
                    'success': True,
                    'activities': activity_data
                })
            else:
                # Get all active workers for current user's tasks
                user_tasks = ScrapingTask.objects.filter(
                    job__user=request.user, 
                    status__in=['initializing', 'crawling', 'extracting', 'processing']
                ).values_list('id', flat=True)
                
                # First get activities related to user's tasks
                activities = CeleryWorkerActivity.objects.filter(
                    Q(task__id__in=user_tasks) |
                    Q(task__isnull=True, status='running')  # Also get "running" workers without tasks
                ).select_related('task', 'task__job').order_by('-timestamp')
                
                # Get unique workers (most recent activity per worker)
                workers_seen = set()
                unique_activities = []
                
                for activity in activities:
                    if activity.worker_name not in workers_seen:
                        workers_seen.add(activity.worker_name)
                        unique_activities.append(activity)
                
                # Format the activities
                activity_data = []
                for activity in unique_activities:
                    task = activity.task
                    
                    activity_data.append({
                        'id': activity.id,
                        'worker_name': activity.worker_name,
                        'hostname': activity.hostname,
                        'activity_type': activity.activity_type,
                        'activity_display': activity.get_activity_type_display(),
                        'status': activity.status,
                        'status_display': activity.get_status_display(),
                        'current_url': activity.current_url,
                        'details': activity.details,
                        'timestamp': activity.timestamp.isoformat(),
                        'task': {
                            'id': task.id,
                            'status': task.status,
                            'status_display': task.get_status_display(),
                            'pages_explored': task.pages_explored,
                            'leads_found': task.leads_found,
                            'unique_leads': task.unique_leads,
                            'job_name': task.job.name,
                        } if task else None
                    })
                
                # Get count of available workers (even if not currently assigned)
                total_workers = len(CeleryWorkerActivity.objects.values('worker_name').distinct())
                
                return Response({
                    'success': True,
                    'activities': activity_data,
                    'total_workers': total_workers,
                    'active_workers': len(unique_activities)
                })
                
        except Exception as e:
            logger.error(f"Error getting worker activity: {str(e)}", exc_info=True)
            return Response({
                'success': False,
                'error': f"Error retrieving worker activity: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
