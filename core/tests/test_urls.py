from django.urls import path, include
from django.views.generic import TemplateView
from rest_framework.routers import DefaultRouter
from .test_decorators import test_quota_view

# Mock views for testing
class HomeView(TemplateView):
    template_name = 'home.html'

class DashboardView(TemplateView):
    template_name = 'dashboard.html'

# API router
router = DefaultRouter()

# Auth URLs (templates)
auth_patterns = [
    path('login/', TemplateView.as_view(template_name='auth/login.html'), name='login'),
    path('register/', TemplateView.as_view(template_name='auth/register.html'), name='register'),
    path('password/reset/', TemplateView.as_view(template_name='auth/password_reset.html'), name='password_reset'),
    path('activate/<str:uid>/', TemplateView.as_view(template_name='auth/activation.html'), name='activate'),
]

urlpatterns = [
    # Template URLs
    path('', HomeView.as_view(), name='home'),
    path('auth/', include((auth_patterns, 'auth'))),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    
    # API URLs
    path('', include(router.urls)),
    path('test-quota/', test_quota_view, name='test-quota'),
] 