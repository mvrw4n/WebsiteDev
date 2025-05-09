from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.http import HttpResponseRedirect
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from .models import CustomUser, UserProfile, ScrapingJob, ScrapingStructure, Lead
from django.utils import timezone

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'
    fk_name = 'user'
    fields = ('role', 'leads_quota', 'leads_used', 'unlimited_leads', 'trial_expiration', 'can_use_advanced_scraping', 'can_use_personalized_messages', 'has_closer_team')

@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('email', 'is_active', 'is_staff', 'get_role', 'leads_quota', 'leads_used', 'date_joined')
    list_filter = ('is_active', 'is_staff', 'profile__role', 'date_joined')
    search_fields = ('email',)
    ordering = ('email',)
    readonly_fields = ('date_joined', 'last_login')
    inlines = [UserProfileInline]
    actions = ['make_lifetime', 'make_classic', 'make_premium', 'make_free']
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2'),
        }),
    )
    
    def get_role(self, obj):
        try:
            return obj.profile.get_role_display()
        except UserProfile.DoesNotExist:
            return "No profile"
    get_role.short_description = "Role"
    
    def leads_quota(self, obj):
        try:
            return obj.profile.leads_quota if not obj.profile.unlimited_leads else "Unlimited"
        except UserProfile.DoesNotExist:
            return "N/A"
    leads_quota.short_description = "Leads Quota"
    
    def leads_used(self, obj):
        try:
            return obj.profile.leads_used
        except UserProfile.DoesNotExist:
            return "N/A"
    leads_used.short_description = "Leads Used"
    
    def make_lifetime(self, request, queryset):
        updated = 0
        for user in queryset:
            try:
                profile = user.profile
                profile.role = 'lifetime'
                profile.unlimited_leads = True
                profile.can_use_advanced_scraping = True
                profile.can_use_personalized_messages = True
                profile.save()
                updated += 1
            except UserProfile.DoesNotExist:
                # Create profile if it doesn't exist
                UserProfile.objects.create(
                    user=user,
                    role='lifetime',
                    unlimited_leads=True,
                    can_use_advanced_scraping=True,
                    can_use_personalized_messages=True
                )
                updated += 1
        
        self.message_user(request, f"Changed {updated} user(s) to Lifetime role", messages.SUCCESS)
    make_lifetime.short_description = "Change selected users to Lifetime role"
    
    def make_classic(self, request, queryset):
        updated = 0
        for user in queryset:
            try:
                profile = user.profile
                profile.role = 'classic'
                profile.leads_quota = 100
                profile.unlimited_leads = False
                profile.can_use_advanced_scraping = True
                profile.can_use_personalized_messages = True
                profile.has_closer_team = False
                profile.save()
                updated += 1
            except UserProfile.DoesNotExist:
                # Create profile if it doesn't exist
                UserProfile.objects.create(
                    user=user,
                    role='classic',
                    leads_quota=100,
                    can_use_advanced_scraping=True,
                    can_use_personalized_messages=True
                )
                updated += 1
        
        self.message_user(request, f"Changed {updated} user(s) to Classic role", messages.SUCCESS)
    make_classic.short_description = "Change selected users to Classic role"
    
    def make_premium(self, request, queryset):
        updated = 0
        for user in queryset:
            try:
                profile = user.profile
                profile.role = 'premium'
                profile.leads_quota = 300
                profile.unlimited_leads = False
                profile.can_use_advanced_scraping = True
                profile.can_use_personalized_messages = True
                profile.has_closer_team = True
                profile.save()
                updated += 1
            except UserProfile.DoesNotExist:
                # Create profile if it doesn't exist
                UserProfile.objects.create(
                    user=user,
                    role='premium',
                    leads_quota=300,
                    can_use_advanced_scraping=True,
                    can_use_personalized_messages=True,
                    has_closer_team=True
                )
                updated += 1
        
        self.message_user(request, f"Changed {updated} user(s) to Premium role", messages.SUCCESS)
    make_premium.short_description = "Change selected users to Premium role"
    
    def make_free(self, request, queryset):
        updated = 0
        for user in queryset:
            try:
                profile = user.profile
                profile.role = 'free'
                profile.leads_quota = 5
                profile.unlimited_leads = False
                profile.can_use_advanced_scraping = False
                profile.can_use_personalized_messages = False
                profile.has_closer_team = False
                profile.save()
                updated += 1
            except UserProfile.DoesNotExist:
                # Create profile if it doesn't exist
                UserProfile.objects.create(
                    user=user,
                    role='free',
                    leads_quota=5
                )
                updated += 1
        
        self.message_user(request, f"Changed {updated} user(s) to Free role", messages.SUCCESS)
    make_free.short_description = "Change selected users to Free role"

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user_email', 'role', 'leads_quota', 'leads_used', 'unlimited_leads')
    list_filter = ('role', 'unlimited_leads')
    search_fields = ('user__email',)
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = "User"

@admin.register(ScrapingJob)
class ScrapingJobAdmin(admin.ModelAdmin):
    list_display = ('name', 'user_email', 'structure_name', 'leads_allocated', 'leads_found', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('name', 'user__email', 'structure__name')
    actions = ['start_selected_jobs']
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = "User"
    
    def structure_name(self, obj):
        if obj.structure:
            return obj.structure.name
        return "No structure"
    structure_name.short_description = "Structure"
    
    def start_selected_jobs(self, request, queryset):
        from scraping.tasks import start_job
        
        started = 0
        for job in queryset:
            if job.status != 'running':
                job.status = 'pending'
                job.save()
                start_job.delay(job.id)
                started += 1
                
        if started > 0:
            self.message_user(request, f"Started {started} job(s)", messages.SUCCESS)
        else:
            self.message_user(request, "No jobs were started. Check their status.", messages.WARNING)
    
    start_selected_jobs.short_description = "Start selected jobs"

@admin.register(ScrapingStructure)
class ScrapingStructureAdmin(admin.ModelAdmin):
    list_display = ('name', 'user_email', 'scraping_strategy', 'leads_target_per_day', 'created_at')
    list_filter = ('scraping_strategy', 'created_at')
    search_fields = ('name', 'user__email')
    actions = ['start_manual_scrape_for_selected']
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('name', 'user', 'entity_type', 'description')
        }),
        ('Scraping Settings', {
            'fields': ('scraping_strategy', 'leads_target_per_day')
        }),
        ('Structure Data', {
            'fields': ('structure', 'created_at', 'updated_at')
        }),
    )
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = "User"
    
    def response_change(self, request, obj):
        if "_start_scrape" in request.POST:
            # Call the Celery task to start scraping for this structure
            from scraping.tasks import start_structure_scrape
            task = start_structure_scrape.delay(obj.id)
            
            self.message_user(
                request,
                f"Started manual scraping for '{obj.name}'. Task ID: {task.id}",
                messages.SUCCESS
            )
            return HttpResponseRedirect(".")
        return super().response_change(request, obj)
    
    def start_manual_scrape_for_selected(self, request, queryset):
        from scraping.tasks import start_structure_scrape
        
        started = 0
        for structure in queryset:
            task = start_structure_scrape.delay(structure.id)
            started += 1
            
        if started > 0:
            self.message_user(request, f"Started manual scraping for {started} structure(s)", messages.SUCCESS)
        else:
            self.message_user(request, "No structures were scraped", messages.WARNING)
            
    start_manual_scrape_for_selected.short_description = "Start manual scraping"
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields['user'].required = True
        return form
    
    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_start_scrape_button'] = True
        return super().change_view(request, object_id, form_url, extra_context)

@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ('name', 'user_email', 'status', 'email', 'phone', 'company', 'priority', 'days_since_contact', 'created_at')
    list_filter = ('status', 'priority', 'created_at')
    search_fields = ('name', 'email', 'company', 'phone', 'user__email')
    readonly_fields = ('created_at', 'updated_at', 'scraping_result_link')
    actions = ['mark_as_contacted', 'mark_as_not_contacted', 'mark_as_interested', 'mark_as_not_interested', 'mark_as_converted']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'user', 'status', 'priority')
        }),
        ('Contact Information', {
            'fields': ('email', 'phone', 'company', 'position')
        }),
        ('Source Information', {
            'fields': ('source', 'source_url', 'scraping_result_link')
        }),
        ('Additional Information', {
            'fields': ('data', 'notes', 'tags')
        }),
        ('Tracking', {
            'fields': ('created_at', 'updated_at', 'last_contacted_at')
        }),
    )
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = "User"
    
    def days_since_contact(self, obj):
        if obj.last_contacted_at:
            return obj.days_since_contacted
        return "Not contacted"
    days_since_contact.short_description = "Days Since Contact"
    
    def scraping_result_link(self, obj):
        if not obj.scraping_result:
            return "No scraping result linked"
        
        url = reverse("admin:scraping_scrapingresult_change", args=[obj.scraping_result.id])
        return format_html('<a href="{}">{}</a>', url, f"Scraping Result #{obj.scraping_result.id}")
    scraping_result_link.short_description = "Scraping Result"
    
    def mark_as_contacted(self, request, queryset):
        queryset.update(status='contacted', last_contacted_at=timezone.now())
        self.message_user(request, f"Marked {queryset.count()} leads as contacted", messages.SUCCESS)
    mark_as_contacted.short_description = "Mark as contacted"
    
    def mark_as_not_contacted(self, request, queryset):
        queryset.update(status='not_contacted')
        self.message_user(request, f"Marked {queryset.count()} leads as not contacted", messages.SUCCESS)
    mark_as_not_contacted.short_description = "Mark as not contacted"
    
    def mark_as_interested(self, request, queryset):
        queryset.update(status='interested')
        self.message_user(request, f"Marked {queryset.count()} leads as interested", messages.SUCCESS)
    mark_as_interested.short_description = "Mark as interested"
    
    def mark_as_not_interested(self, request, queryset):
        queryset.update(status='not_interested')
        self.message_user(request, f"Marked {queryset.count()} leads as not interested", messages.SUCCESS)
    mark_as_not_interested.short_description = "Mark as not interested"
    
    def mark_as_converted(self, request, queryset):
        queryset.update(status='converted')
        self.message_user(request, f"Marked {queryset.count()} leads as converted", messages.SUCCESS)
    mark_as_converted.short_description = "Mark as converted"
