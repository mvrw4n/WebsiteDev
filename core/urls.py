from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView
from djoser.views import UserViewSet
from rest_framework.routers import DefaultRouter
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import asyncio
from asgiref.sync import sync_to_async
from .views import (
    LoginView, RegisterView, PasswordResetView,
    PasswordResetConfirmView, AccountActivationView,
    DashboardView, VerifyActivationCodeView, HomeView, ProtectedRegistrationView,
    ChatView, ChatHistoryView, ChatJobsStatusView, ChatClearView, ChatStructureUpdateView,
    ScrapingStructureView, ScrapingJobView, SubscriptionAPIView,
    DashboardStatsView, ActiveScrapingJobsView, WorkerActivityView,
    ScrapingJobControlView, ScrapingJobHistoryView, UserProfileAPIView, 
    ScrapingRecommendationAPIView, UserLeadsAPIView, UserLeadsStatsAPIView,
    PasswordChangeAPIView, AccountDeleteAPIView, UserSessionAPIView,
    LeadAPIView, LeadDetailAPIView, LeadStatusUpdateAPIView, LeadStatsAPIView,
    PricingView, AboutView
)
from django.views.generic import TemplateView

# API router
router = DefaultRouter()
router.register("users", UserViewSet, basename="users")

# Auth URLs (templates)
auth_patterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('register/', RegisterView.as_view(), name='register'),
    path('password/reset/', PasswordResetView.as_view(), name='password_reset'),
    path('password/reset/confirm/<uidb64>/<token>/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('activate/', AccountActivationView.as_view(), name='account_activate'),
    path('verify-code/', VerifyActivationCodeView.as_view(), name='verify_activation_code'),
    path('cgu/', TemplateView.as_view(template_name='auth/cgu.html'), name='cgu'),
]

urlpatterns = [
    # Template URLs
    path('auth/', include((auth_patterns, 'auth'))),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    
    # API URLs - Djoser and JWT endpoints
    path('auth/', include('djoser.urls')),
    path('auth/', include('djoser.urls.jwt')),
    path('api/auth/register/', csrf_exempt(UserViewSet.as_view({'post': 'create'})), name='api_register'),
    path('', HomeView.as_view(), name='home'),
    path('pricing/', PricingView.as_view(), name='pricing'),
    path('about/', AboutView.as_view(), name='about'),
    path('lifetime-registration/', ProtectedRegistrationView.as_view(), name='lifetime_registration'),
    
    # Dashboard API endpoints
    path('api/dashboard/stats/', DashboardStatsView.as_view(), name='dashboard_stats'),
    path('api/dashboard/subscription/', SubscriptionAPIView.as_view(), name='dashboard_subscription'),
    
    # User profile API endpoints
    path('api/user/profile/', csrf_exempt(UserProfileAPIView.as_view()), name='user_profile'),
    path('api/user/recommendations/', csrf_exempt(ScrapingRecommendationAPIView.as_view()), name='scraping_recommendations'),
    path('api/user/leads/', csrf_exempt(UserLeadsAPIView.as_view()), name='user_leads'),
    path('api/user/leads/stats/', csrf_exempt(UserLeadsStatsAPIView.as_view()), name='user_leads_stats'),
    path('api/user/leads/<int:lead_id>/', csrf_exempt(UserLeadsAPIView.as_view()), name='user_lead_detail'),
    
    # Account management API endpoints
    path('api/auth/password/change/', csrf_exempt(PasswordChangeAPIView.as_view()), name='password_change'),
    path('api/auth/account/delete/', csrf_exempt(AccountDeleteAPIView.as_view()), name='account_delete'),
    path('api/auth/sessions/', csrf_exempt(UserSessionAPIView.as_view()), name='user_sessions'),
    
    # Chat API endpoints
    path('api/chat/', csrf_exempt(ChatView.as_view()), name='chat'),
    path('api/chat/send/', csrf_exempt(ChatView.as_view()), name='chat_send'),
    path('api/chat/history/', csrf_exempt(ChatHistoryView.as_view()), name='chat_history'),
    path('api/chat/jobs-status/', csrf_exempt(ChatJobsStatusView.as_view()), name='chat_jobs_status'),
    path('api/chat/clear/', csrf_exempt(ChatClearView.as_view()), name='chat_clear'),
    path('api/chat/update-structure/', csrf_exempt(ChatStructureUpdateView.as_view()), name='chat_update_structure'),
    
    # Scraping API endpoints
    path('api/scraping/structures/', csrf_exempt(ScrapingStructureView.as_view()), name='scraping_structures'),
    path('api/scraping/structures/<int:structure_id>/', csrf_exempt(ScrapingStructureView.as_view()), name='scraping_structure_detail'),
    path('api/scraping/jobs/', csrf_exempt(ScrapingJobView.as_view()), name='scraping_jobs'),
    path('api/scraping/jobs/active/', csrf_exempt(ActiveScrapingJobsView.as_view()), name='active_scraping_jobs'),
    path('api/scraping/jobs/history/', csrf_exempt(ScrapingJobHistoryView.as_view()), name='scraping_job_history'),
    path('api/scraping/jobs/<int:job_id>/', csrf_exempt(ScrapingJobView.as_view()), name='scraping_job_detail'),
    path('api/scraping/jobs/<int:job_id>/control/', csrf_exempt(ScrapingJobControlView.as_view()), name='scraping_job_control'),
    path('api/scraping/workers/activity/', csrf_exempt(WorkerActivityView.as_view()), name='worker_activity'),
    
    # Subscription API endpoints
    path('api/subscription/change-plan/', csrf_exempt(SubscriptionAPIView.as_view()), name='subscription_change_plan'),
    
    # Leads API endpoints
    path('api/leads/', csrf_exempt(LeadAPIView.as_view()), name='leads'),
    path('api/leads/<int:pk>/', csrf_exempt(LeadDetailAPIView.as_view()), name='lead_detail'),
    path('api/leads/status-update/', csrf_exempt(LeadStatusUpdateAPIView.as_view()), name='lead_status_update'),
    path('api/leads/stats/', csrf_exempt(LeadStatsAPIView.as_view()), name='lead_stats'),
] 