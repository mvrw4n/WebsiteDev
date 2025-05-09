from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from core.models import UserProfile
from core.decorators import check_quota
from rest_framework.decorators import api_view
from rest_framework.response import Response
from datetime import timedelta
from django.urls import reverse

User = get_user_model()

# Test view for quota decorator
@api_view(['GET'])
@check_quota
def test_quota_view(request):
    return Response({'status': 'success'})

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

    def test_quota_check_with_sufficient_quota(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.quota_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')

    def test_quota_check_with_zero_quota(self):
        self.profile.leads_quota = 0
        self.profile.save()
        
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.quota_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('quota', response.data['error'].lower())

    def test_quota_check_subscriber_bypass(self):
        self.profile.leads_quota = 0
        self.profile.role = 'subscriber'
        self.profile.save()
        
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.quota_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')

    def test_quota_check_trial_user(self):
        self.profile.leads_quota = 0
        self.profile.trial_expiration = timezone.now() + timedelta(days=7)
        self.profile.save()
        
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.quota_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')

    def test_quota_check_expired_trial(self):
        self.profile.leads_quota = 0
        self.profile.trial_expiration = timezone.now() - timedelta(days=1)
        self.profile.save()
        
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.quota_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('quota', response.data['error'].lower())

    def test_quota_check_unauthenticated(self):
        response = self.client.get(self.quota_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED) 