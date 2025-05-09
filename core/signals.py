from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from .models import UserProfile, CustomUser

@receiver(post_save, sender=CustomUser)
def create_user_profile(sender, instance, created, **kwargs):
    """Create a UserProfile for every new user."""
    if created:
        UserProfile.objects.create(
            user=instance,
            role='free',  # Default role
            leads_quota=5,  # Default quota
            trial_expiration=None,  # No trial by default
            notes="Profile created automatically"
        ) 