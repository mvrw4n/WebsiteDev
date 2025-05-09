from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from core.models import UserProfile
from datetime import timedelta

User = get_user_model()

class CustomUserTests(TestCase):
    def setUp(self):
        self.user_data = {
            'email': 'test@example.com',
            'password': 'testpass123'
        }

    def test_create_user(self):
        user = User.objects.create_user(**self.user_data)
        self.assertEqual(user.email, self.user_data['email'])
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_superuser(self):
        user = User.objects.create_superuser(**self.user_data)
        self.assertEqual(user.email, self.user_data['email'])
        self.assertTrue(user.is_active)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_email_normalized(self):
        email = 'test@EXAMPLE.com'
        user = User.objects.create_user(email=email, password='test123')
        self.assertEqual(user.email, email.lower())

    def test_email_required(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(email='', password='test123')

class UserProfileTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.profile = UserProfile.objects.create(user=self.user)

    def test_profile_creation(self):
        self.assertEqual(self.profile.role, 'free')
        self.assertEqual(self.profile.leads_quota, 10)
        self.assertIsNone(self.profile.trial_expiration)

    def test_has_active_trial(self):
        # Test without trial expiration
        self.assertFalse(self.profile.has_active_trial)
        
        # Test with future trial expiration
        self.profile.trial_expiration = timezone.now() + timedelta(days=7)
        self.profile.save()
        self.assertTrue(self.profile.has_active_trial)
        
        # Test with expired trial
        self.profile.trial_expiration = timezone.now() - timedelta(days=1)
        self.profile.save()
        self.assertFalse(self.profile.has_active_trial)

    def test_can_access_leads(self):
        # Test free user without trial
        self.assertFalse(self.profile.can_access_leads)
        
        # Test free user with active trial
        self.profile.trial_expiration = timezone.now() + timedelta(days=7)
        self.profile.save()
        self.assertTrue(self.profile.can_access_leads)
        
        # Test subscriber
        self.profile.role = 'subscriber'
        self.profile.trial_expiration = None
        self.profile.save()
        self.assertTrue(self.profile.can_access_leads)

    def test_string_representation(self):
        expected_string = f"{self.user.email} - {self.profile.role}"
        self.assertEqual(str(self.profile), expected_string) 