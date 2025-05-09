from django.test import TestCase, Client, override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.utils import timezone
from datetime import timedelta
from core.models import CustomUser, UserProfile
from core.decorators import check_quota
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.contrib.messages import get_messages
from .test_settings import test_settings

User = get_user_model()

# Test view for quota decorator
@api_view(['GET'])
@check_quota
def test_quota_view(request):
    return Response({'message': 'success'})

class AuthenticationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.register_url = reverse('user-list')
        self.login_url = reverse('jwt-create')
        self.user_data = {
            'email': 'test@example.com',
            'password': 'testpass123',
            'password2': 'testpass123'
        }

    def test_user_registration(self):
        response = self.client.post(self.register_url, self.user_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(CustomUser.objects.filter(email=self.user_data['email']).exists())
        
    def test_user_login(self):
        # Create user first
        CustomUser.objects.create_user(
            email=self.user_data['email'],
            password=self.user_data['password']
        )
        
        # Attempt login
        response = self.client.post(self.login_url, {
            'email': self.user_data['email'],
            'password': self.user_data['password']
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

@override_settings(**test_settings)
class ViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.home_url = reverse('home')
        self.login_url = reverse('auth:login')
        self.register_url = reverse('auth:register')
        self.dashboard_url = reverse('dashboard')
        self.password_reset_url = reverse('auth:password_reset')

    def test_home_view(self):
        response = self.client.get(self.home_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'home.html')

    def test_login_view(self):
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'auth/login.html')

    def test_register_view(self):
        response = self.client.get(self.register_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'auth/register.html')

    def test_password_reset_view(self):
        response = self.client.get(self.password_reset_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'auth/password_reset.html')

    def test_dashboard_view_redirect_if_not_logged_in(self):
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, f'{self.login_url}?next={self.dashboard_url}')

    def test_dashboard_view_if_logged_in(self):
        self.client.login(email='test@example.com', password='testpass123')
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard.html')

@override_settings(**test_settings)
class AccountActivationViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            is_active=False
        )
        self.uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        self.activation_url = reverse('auth:activate', kwargs={'uid': self.uid})

    def test_account_activation_valid_link(self):
        response = self.client.get(self.activation_url)
        self.user.refresh_from_db()
        
        self.assertTrue(self.user.is_active)
        self.assertRedirects(response, reverse('auth:login'))
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any(message.message == 'Your account has been activated successfully! You can now login.' 
                          for message in messages))

    def test_account_activation_already_activated(self):
        self.user.is_active = True
        self.user.save()
        
        response = self.client.get(self.activation_url)
        self.assertRedirects(response, reverse('auth:login'))
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any(message.message == 'Your account is already activated.' 
                          for message in messages))

    def test_account_activation_invalid_link(self):
        invalid_uid = urlsafe_base64_encode(force_bytes(999999))  # Non-existent user ID
        invalid_url = reverse('auth:activate', kwargs={'uid': invalid_uid})
        
        response = self.client.get(invalid_url)
        self.assertRedirects(response, reverse('home'))
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any(message.message == 'Invalid activation link.' 
                          for message in messages))

@override_settings(**test_settings)
class QuotaDecoratorTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            leads_quota=5
        )
        self.quota_url = reverse('test-quota')
        
    def test_quota_check_unauthorized(self):
        """Test that unauthorized users cannot access quota-protected views"""
        response = self.client.get(self.quota_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
    def test_quota_check_free_user(self):
        """Test that free users without trial cannot access"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.quota_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
    def test_quota_check_trial_user(self):
        """Test that trial users can access and quota decrements"""
        self.client.force_authenticate(user=self.user)
        self.profile.trial_expiration = timezone.now() + timedelta(days=7)
        self.profile.save()
        
        initial_quota = self.profile.leads_quota
        response = self.client.get(self.quota_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.leads_quota, initial_quota - 1)
        
    def test_quota_check_subscriber(self):
        """Test that subscribers can access"""
        self.client.force_authenticate(user=self.user)
        self.profile.role = 'subscriber'
        self.profile.save()
        
        response = self.client.get(self.quota_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
    def test_quota_exhausted(self):
        """Test that users with exhausted quota cannot access"""
        self.client.force_authenticate(user=self.user)
        self.profile.trial_expiration = timezone.now() + timedelta(days=7)
        self.profile.leads_quota = 0
        self.profile.save()
        
        response = self.client.get(self.quota_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('quota', response.data['error'].lower()) 