from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import redirect
from . import views
from .admin import ScrapingControlPanelView

app_name = 'scraping'

# Create an instance of the control panel view
control_panel_view = ScrapingControlPanelView()

urlpatterns = [
    # Liste des tâches actives - must be before task_id patterns to avoid conflicts
    path('api/tasks/active/', csrf_exempt(views.ActiveTasksView.as_view()), name='active_tasks'),
    
    # API endpoints for scraping tasks
    path('api/tasks/<int:task_id>/', csrf_exempt(views.ScrapingTaskDetailView.as_view()), name='task_detail'),
    
    # Logs d'une tâche de scraping
    path('api/tasks/<int:task_id>/logs/', csrf_exempt(views.ScrapingTaskLogsView.as_view()), name='task_logs'),
    
    # Résultats d'une tâche de scraping
    path('api/tasks/<int:task_id>/results/', csrf_exempt(views.ScrapingTaskResultsView.as_view()), name='task_results'),
    
    # Worker activity tracking
    path('api/workers/activity/', csrf_exempt(views.WorkerActivityView.as_view()), name='worker_activity'),
    path('api/workers/activity/<int:task_id>/', csrf_exempt(views.WorkerActivityView.as_view()), name='worker_task_activity'),
    
    # Création d'une tâche de scraping (démarrer)
    path('api/jobs/<int:job_id>/start/', csrf_exempt(views.ScrapingTaskControlView.as_view()), name='start_task'),
    
    # Contrôle d'une tâche de scraping (pause, reprise, arrêt)
    path('api/tasks/<int:task_id>/control/', csrf_exempt(views.ScrapingTaskControlView.as_view()), name='control_task'),
    
    # API endpoint for structures
    path('api/structures/', views.ScrapingStructureListView.as_view(), name='structure_list'),
    
    # API endpoint to start scraping for a structure from the dashboard
    path('api/structures/<int:structure_id>/start-scraping/', csrf_exempt(views.StartStructureScrapingView.as_view()), name='start_structure_scraping'),
    
    # Admin Control Panel URL - used in admin menu links
    path('control-panel/', staff_member_required(control_panel_view.control_panel_view), name='admin_control_panel'),
] 