from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'plans', views.SubscriptionPlanViewSet)
router.register(r'subscriptions', views.SubscriptionViewSet, basename='subscription')

app_name = 'billing'

urlpatterns = [
    path('', include(router.urls)),
    path('webhook/', views.stripe_webhook, name='stripe-webhook'),
    path('subscription/', views.SubscriptionInfoView.as_view(), name='subscription-info'),
] 