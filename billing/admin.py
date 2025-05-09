from django.contrib import admin
from .models import SubscriptionPlan, Subscription, Coupon, SubscriptionUsage

@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'price', 'interval', 'leads_quota', 'is_active']
    list_filter = ['interval', 'is_active']
    search_fields = ['name']

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['user', 'plan', 'status', 'current_period_start', 'current_period_end']
    list_filter = ['status', 'plan']
    search_fields = ['user__email']
    raw_id_fields = ['user', 'plan']

@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ['code', 'discount_type', 'discount_value', 'valid_from', 'valid_until', 'is_active']
    list_filter = ['discount_type', 'is_active']
    search_fields = ['code']

@admin.register(SubscriptionUsage)
class SubscriptionUsageAdmin(admin.ModelAdmin):
    list_display = ['subscription', 'period_start', 'period_end', 'leads_used']
    list_filter = ['period_start', 'period_end']
    search_fields = ['subscription__user__email']
    raw_id_fields = ['subscription']
