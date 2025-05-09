from rest_framework import serializers
from .models import SubscriptionPlan, Subscription, SubscriptionUsage

class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = ['id', 'name', 'price', 'interval', 'leads_quota', 'features']

class SubscriptionUsageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionUsage
        fields = ['leads_used', 'leads_remaining', 'period_start', 'period_end']

class SubscriptionSerializer(serializers.ModelSerializer):
    plan = SubscriptionPlanSerializer(read_only=True)
    current_usage = SubscriptionUsageSerializer(source='usage.last', read_only=True)
    
    class Meta:
        model = Subscription
        fields = [
            'id', 'plan', 'status', 'current_period_start',
            'current_period_end', 'cancel_at_period_end',
            'current_usage'
        ]
        read_only_fields = fields 