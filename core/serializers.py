from djoser.serializers import UserCreateSerializer
from rest_framework import serializers
from .models import CustomUser, UserProfile, Lead

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ['role', 'trial_expiration', 'leads_quota', 'can_access_leads']
        read_only_fields = ['leads_quota', 'can_access_leads']

class CustomUserCreateSerializer(UserCreateSerializer):
    class Meta(UserCreateSerializer.Meta):
        model = CustomUser
        fields = ['id', 'email', 'password', 'cgu_accepted', 'accept_contact']

class CustomUserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)
    
    class Meta:
        model = CustomUser
        fields = ['id', 'email', 'profile', 'date_joined']
        read_only_fields = ['date_joined']

class LeadSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    days_since_contacted = serializers.IntegerField(read_only=True)
    days_since_created = serializers.IntegerField(read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    
    class Meta:
        model = Lead
        fields = [
            'id', 'name', 'email', 'phone', 'company', 'position', 
            'status', 'status_display', 'priority', 'source', 'source_url',
            'notes', 'tags', 'created_at', 'updated_at', 'last_contacted_at',
            'days_since_contacted', 'days_since_created', 'user_email', 'data'
        ]
        read_only_fields = ['created_at', 'updated_at', 'user_email'] 