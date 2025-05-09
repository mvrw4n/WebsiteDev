from django.test import TestCase
from django.contrib.auth import get_user_model
from core.models import UserProfile
from core.serializers import UserProfileSerializer, CustomUserSerializer, CustomUserCreateSerializer
from django.utils import timezone
from datetime import timedelta

User = get_user_model()

class CustomUserCreateSerializerTests(TestCase):
    def setUp(self):
        self.user_data = {
            'email': 'test@example.com',
            'password': 'testpass123'
        }

    def test_serializer_with_valid_data(self):
        serializer = CustomUserCreateSerializer(data=self.user_data)
        self.assertTrue(serializer.is_valid())

    def test_serializer_with_invalid_email(self):
        self.user_data['email'] = 'invalid-email'
        serializer = CustomUserCreateSerializer(data=self.user_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('email', serializer.errors)

class CustomUserSerializerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.profile = UserProfile.objects.create(user=self.user)
        self.serializer = CustomUserSerializer(instance=self.user)

    def test_contains_expected_fields(self):
        data = self.serializer.data
        self.assertCountEqual(data.keys(), ['id', 'email', 'profile', 'date_joined'])

    def test_profile_field_content(self):
        data = self.serializer.data
        self.assertEqual(data['email'], self.user.email)
        self.assertIn('profile', data)
        self.assertEqual(data['profile']['role'], 'free')
        self.assertEqual(data['profile']['leads_quota'], 10)

class UserProfileSerializerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            role='free',
            leads_quota=10,
            trial_expiration=timezone.now() + timedelta(days=7)
        )
        self.serializer = UserProfileSerializer(instance=self.profile)

    def test_contains_expected_fields(self):
        data = self.serializer.data
        expected_fields = {
            'role',
            'trial_expiration',
            'leads_quota',
            'can_access_leads'
        }
        self.assertCountEqual(data.keys(), expected_fields)

    def test_read_only_fields(self):
        data = {
            'role': 'subscriber',
            'leads_quota': 100,  # Should be read-only
            'can_access_leads': True  # Should be read-only
        }
        serializer = UserProfileSerializer(self.profile, data=data, partial=True)
        self.assertTrue(serializer.is_valid())
        updated_profile = serializer.save()
        self.assertEqual(updated_profile.role, 'subscriber')  # This should change
        self.assertEqual(updated_profile.leads_quota, 10)  # This should not change 