#!/usr/bin/env python
"""
Script to create a superadmin user for Wizzy.
Usage: python create_superadmin.py <email> <password>
"""

import os
import sys
import django

# Configure Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wizzydjango.settings.development')
django.setup()

# Import models after Django is configured
from core.models import CustomUser, UserProfile
from django.db import transaction

def create_superadmin(email, password):
    """Create a superadmin user with the given email and password"""
    if not email or not password:
        print("Error: Email and password are required.")
        return False
        
    try:
        with transaction.atomic():
            # Check if user already exists
            if CustomUser.objects.filter(email=email).exists():
                print(f"User with email {email} already exists.")
                return False
                
            # Create the superuser
            user = CustomUser.objects.create_superuser(
                email=email,
                password=password
            )
            
            # Get the profile created by signal and update it
            profile = UserProfile.objects.get(user=user)
            profile.role = 'lifetime'  # Set to lifetime for unlimited access
            profile.unlimited_leads = True
            profile.can_use_advanced_scraping = True
            profile.can_use_personalized_messages = True
            profile.save()
            
            print(f"Superadmin user created successfully: {email}")
            print(f"Role: {profile.get_role_display()}")
            print("This user has unlimited leads and all features enabled.")
            return True
    
    except Exception as e:
        print(f"Error creating superadmin user: {str(e)}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python create_superadmin.py <email> <password>")
        sys.exit(1)
    
    email = sys.argv[1]
    password = sys.argv[2]
    
    if create_superadmin(email, password):
        sys.exit(0)
    else:
        sys.exit(1) 