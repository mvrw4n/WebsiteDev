from django.conf import settings
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
import stripe
from .models import SubscriptionPlan, Subscription, Coupon, SubscriptionUsage
from .serializers import SubscriptionPlanSerializer, SubscriptionSerializer
from rest_framework.views import APIView
from django.utils import timezone
import logging

stripe.api_key = settings.STRIPE_SECRET_KEY

logger = logging.getLogger(__name__)

class SubscriptionPlanViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SubscriptionPlan.objects.filter(is_active=True)
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [permissions.IsAuthenticated]

class SubscriptionViewSet(viewsets.ModelViewSet):
    serializer_class = SubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Subscription.objects.filter(user=self.request.user)

    @action(detail=False, methods=['post'])
    def create_subscription(self, request):
        try:
            plan = SubscriptionPlan.objects.get(id=request.data.get('plan_id'))
            payment_method_id = request.data.get('payment_method_id')
            
            # Create or get Stripe customer
            if not request.user.stripe_customer_id:
                customer = stripe.Customer.create(
                    email=request.user.email,
                    payment_method=payment_method_id,
                    invoice_settings={'default_payment_method': payment_method_id}
                )
                request.user.stripe_customer_id = customer.id
                request.user.save()
            
            # Create subscription
            subscription = stripe.Subscription.create(
                customer=request.user.stripe_customer_id,
                items=[{'price': plan.stripe_price_id}],
                expand=['latest_invoice.payment_intent']
            )
            
            # Create local subscription
            Subscription.objects.create(
                user=request.user,
                plan=plan,
                stripe_subscription_id=subscription.id,
                status=subscription.status,
                current_period_start=subscription.current_period_start,
                current_period_end=subscription.current_period_end
            )
            
            return Response({
                'subscription_id': subscription.id,
                'client_secret': subscription.latest_invoice.payment_intent.client_secret
            })
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def cancel_subscription(self, request, pk=None):
        subscription = self.get_object()
        
        try:
            stripe_sub = stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                cancel_at_period_end=True
            )
            
            subscription.cancel_at_period_end = True
            subscription.save()
            
            return Response({'status': 'Subscription will be canceled at the end of the billing period'})
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@csrf_exempt
@require_POST
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        return JsonResponse({'error': 'Invalid payload'}, status=400)
    except stripe.error.SignatureVerificationError:
        return JsonResponse({'error': 'Invalid signature'}, status=400)
        
    if event.type == 'customer.subscription.updated':
        subscription_updated(event.data.object)
    elif event.type == 'customer.subscription.deleted':
        subscription_deleted(event.data.object)
    
    return JsonResponse({'status': 'success'})

def subscription_updated(stripe_sub):
    try:
        subscription = Subscription.objects.get(stripe_subscription_id=stripe_sub.id)
        subscription.status = stripe_sub.status
        subscription.current_period_start = stripe_sub.current_period_start
        subscription.current_period_end = stripe_sub.current_period_end
        subscription.save()
    except Subscription.DoesNotExist:
        pass

def subscription_deleted(stripe_sub):
    try:
        subscription = Subscription.objects.get(stripe_subscription_id=stripe_sub.id)
        subscription.status = 'canceled'
        subscription.save()
    except Subscription.DoesNotExist:
        pass

class SubscriptionInfoView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, *args, **kwargs):
        """Get current subscription information"""
        try:
            # Get user profile
            profile = request.user.profile
            
            # Get subscription if exists
            subscription = None
            if hasattr(request.user, 'subscription'):
                subscription = {
                    'id': request.user.subscription.id,
                    'plan': {
                        'id': request.user.subscription.plan.id,
                        'name': request.user.subscription.plan.name,
                        'price': str(request.user.subscription.plan.price),
                        'interval': request.user.subscription.plan.interval,
                        'leads_quota': request.user.subscription.plan.leads_quota,
                        'features': request.user.subscription.plan.features
                    },
                    'status': request.user.subscription.status,
                    'current_period_start': request.user.subscription.current_period_start.isoformat(),
                    'current_period_end': request.user.subscription.current_period_end.isoformat(),
                    'cancel_at_period_end': request.user.subscription.cancel_at_period_end
                }
            # Create virtual subscription based on user role when no subscription exists
            elif profile.role in ['classic', 'premium', 'lifetime']:
                # Get default plan prices and quotas based on role
                plan_data = {
                    'classic': {'name': 'Wizzy Classique', 'price': '75.00', 'leads_quota': 100},
                    'premium': {'name': 'Wizzy Premium', 'price': '99.00', 'leads_quota': 300},
                    'lifetime': {'name': 'Wizzy Lifetime', 'price': '0.00', 'leads_quota': 9999}
                }
                
                # Get role-specific plan data
                plan = plan_data.get(profile.role)
                
                # Create virtual subscription with the corresponding plan data
                subscription = {
                    'id': 0,  # Virtual ID
                    'plan': {
                        'id': 0,  # Virtual ID
                        'name': plan['name'],
                        'price': plan['price'],
                        'interval': 'month',
                        'leads_quota': plan['leads_quota'],
                        'features': []  # Empty features list
                    },
                    'status': 'active',
                    'current_period_start': timezone.now().isoformat(),
                    'current_period_end': (timezone.now() + timezone.timedelta(days=30)).isoformat(),
                    'cancel_at_period_end': False
                }
            
            # Get usage for current period - only for real subscriptions
            current_usage = None
            if hasattr(request.user, 'subscription'):
                current_usage = SubscriptionUsage.objects.filter(
                    subscription=request.user.subscription,
                    period_start__lte=timezone.now(),
                    period_end__gte=timezone.now()
                ).first()
            
            # Get available plans
            available_plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price')
            plans_data = [{
                'id': plan.id,
                'name': plan.name,
                'price': str(plan.price),
                'interval': plan.interval,
                'leads_quota': plan.leads_quota,
                'features': plan.features
            } for plan in available_plans]
            
            # Create a current_usage dict based on profile data if no real usage exists
            usage_data = None
            if current_usage:
                usage_data = {
                    'leads_used': current_usage.leads_used,
                    'leads_remaining': current_usage.leads_remaining
                }
            elif profile.role != 'free':
                # Calculate remaining leads based on profile data
                usage_data = {
                    'leads_used': profile.leads_used,
                    'leads_remaining': profile.unlimited_leads and 9999 or max(0, profile.leads_quota - profile.leads_used)
                }
            
            return Response({
                'subscription': subscription,
                'current_usage': usage_data,
                'available_plans': plans_data,
                'profile': {
                    'role': profile.role,
                    'leads_quota': profile.leads_quota,
                    'leads_used': profile.leads_used,
                    'unlimited_leads': profile.unlimited_leads
                }
            })
            
        except Exception as e:
            logger.error(f"Error getting subscription info: {str(e)}", exc_info=True)
            return Response(
                {'error': 'An error occurred while getting subscription information'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
