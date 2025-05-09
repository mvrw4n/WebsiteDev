from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models
from django.utils import timezone
import random
import string
from django.conf import settings

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        
        # Generate activation code
        activation_code = ''.join(random.choices(string.digits, k=6))
        extra_fields.setdefault('activation_code', activation_code)
        extra_fields.setdefault('is_active', False)
        
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        return self.create_user(email, password, **extra_fields)

class CustomUser(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    activation_code = models.CharField(max_length=6, blank=True, null=True)
    stripe_customer_id = models.CharField(max_length=100, blank=True, null=True)
    cgu_accepted = models.BooleanField(default=False)
    accept_contact = models.BooleanField(default=False)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def __str__(self):
        return self.email

class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('free', 'Wizzy Free'),
        ('classic', 'Wizzy Classique'),
        ('premium', 'Wizzy Premium'),
        ('lifetime', 'Wizzy Lifetime'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='free')
    leads_quota = models.IntegerField(default=5)  # Default for free users
    leads_used = models.IntegerField(default=0)
    unlimited_leads = models.BooleanField(default=False)
    trial_expiration = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    user_details = models.JSONField(default=dict, blank=True, null=True, help_text="Informations enrichies sur l'utilisateur et son secteur d'activité")
    last_lead_reset = models.DateTimeField(default=timezone.now)
    
    # Tracking fields for lead statistics
    rate_limited_leads = models.IntegerField(default=0, help_text="Leads non créés car l'utilisateur a atteint sa limite")
    incomplete_leads = models.IntegerField(default=0, help_text="Leads non créés car des champs obligatoires étaient manquants")

    # Additional features flags
    can_use_ai_chat = models.BooleanField(default=True)  # Available for all
    can_use_advanced_scraping = models.BooleanField(default=False)  # Only for paid plans
    can_use_personalized_messages = models.BooleanField(default=False)  # Only for paid plans
    has_closer_team = models.BooleanField(default=False)  # Only for premium

    class Meta:
        db_table = 'user_profiles'

    def __str__(self):
        return f"{self.user.email}'s profile - {self.get_role_display()}"

    def save(self, *args, **kwargs):
        # Set features based on role
        if self.role == 'free':
            self.leads_quota = 5
            self.unlimited_leads = False
            self.can_use_advanced_scraping = False
            self.can_use_personalized_messages = False
            self.has_closer_team = False
        elif self.role == 'classic':
            self.leads_quota = 100
            self.unlimited_leads = False
            self.can_use_advanced_scraping = True
            self.can_use_personalized_messages = True
            self.has_closer_team = False
        elif self.role == 'premium':
            self.leads_quota = 300
            self.unlimited_leads = False
            self.can_use_advanced_scraping = True
            self.can_use_personalized_messages = True
            self.has_closer_team = True
        elif self.role == 'lifetime':
            self.unlimited_leads = True
            self.can_use_advanced_scraping = True
            self.can_use_personalized_messages = True
            self.has_closer_team = False

        super().save(*args, **kwargs)

    @property
    def can_access_leads(self):
        if self.unlimited_leads:
            return True
        if self.trial_expiration and self.trial_expiration < timezone.now():
            return False
        return self.leads_used < self.leads_quota

    def reset_daily_leads(self):
        """Reset leads count if it's a new day"""
        now = timezone.now()
        if now.date() > self.last_lead_reset.date():
            self.leads_used = 0
            self.last_lead_reset = now
            self.save()

    def can_purchase_additional_leads(self):
        """Check if user can purchase additional leads"""
        return self.role in ['classic', 'premium']

    def get_additional_leads_limits(self):
        """Get the limits for additional leads purchase"""
        if not self.can_purchase_additional_leads():
            return None
        return {
            'min': 20,
            'max': 30000,
            'base_price': 1.0,
            'min_price': 0.3
        }

class Interaction(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    message = models.TextField()
    response = models.TextField()
    structure = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']

class AIAction(models.Model):
    ACTION_TYPES = [
        ('serp_scraping', 'SERP Scraping'),
        ('linkedin_scraping', 'LinkedIn Scraping'),
        ('dropcontact_enrichment', 'Dropcontact Enrichment'),
        ('custom_scraping', 'Custom Scraping'),
    ]
    
    interaction = models.ForeignKey(Interaction, on_delete=models.CASCADE)
    action_type = models.CharField(max_length=50, choices=ACTION_TYPES)
    parameters = models.JSONField()
    status = models.CharField(max_length=20, default='pending')
    result = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

class PromptLog(models.Model):
    interaction = models.ForeignKey(Interaction, on_delete=models.CASCADE)
    prompt = models.TextField()
    response = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']

class ScrapingStructure(models.Model):
    ENTITY_TYPES = [
        ('mairie', 'Mairie'),
        ('entreprise', 'Entreprise'),
        ('b2b_lead', 'B2B Lead'),
        ('custom', 'Structure personnalisée'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='scraping_structures')
    name = models.CharField(max_length=100)
    entity_type = models.CharField(max_length=20, choices=ENTITY_TYPES)
    structure = models.JSONField()
    is_active = models.BooleanField(default=True)
    scraping_strategy = models.CharField(max_length=100, default='custom_scraping')
    leads_target_per_day = models.IntegerField(default=10)
    
    # Added fields for lead tracking
    leads_extracted_today = models.IntegerField(default=0)
    total_leads_extracted = models.IntegerField(default=0)
    last_extraction_date = models.DateField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['user', 'name']
        
    def __str__(self):
        return f"{self.name} ({self.entity_type}) - {self.user.email}"
        
    def reset_daily_leads(self):
        """Reset the daily lead count if it's a new day"""
        today = timezone.now().date()
        if not self.last_extraction_date or self.last_extraction_date < today:
            self.leads_extracted_today = 0
            self.last_extraction_date = today
            self.save(update_fields=['leads_extracted_today', 'last_extraction_date'])
            
    def get_completion_percentage(self):
        """Get the percentage of daily lead target that has been reached"""
        if self.leads_target_per_day <= 0:
            return 100
        return min(100, int((self.leads_extracted_today / self.leads_target_per_day) * 100))

class ScrapingJob(models.Model):
    """Scraping job model - represents a task to scrape data based on a structure"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='scraping_jobs')
    structure = models.ForeignKey(ScrapingStructure, on_delete=models.SET_NULL, null=True, blank=True, related_name='jobs')
    name = models.CharField(max_length=255)
    search_query = models.CharField(max_length=255, blank=True)
    leads_allocated = models.PositiveIntegerField(default=10)  # How many leads to collect
    leads_found = models.PositiveIntegerField(default=0)  # How many leads were found (updated when task completes)
    status = models.CharField(max_length=20, default='pending', 
                             choices=[
                                 ('pending', 'Pending'),
                                 ('initializing', 'Initializing'),
                                 ('running', 'Running'),
                                 ('paused', 'Paused'),
                                 ('completed', 'Completed'),
                                 ('failed', 'Failed'),
                                 ('stopped', 'Stopped')
                             ])
    task_id = models.CharField(max_length=255, blank=True, null=True)  # Celery task ID for status tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.status})"
    
    def to_dict(self):
        """Convert job to dictionary"""
        structure_data = None
        if self.structure:
            structure_data = {
                'id': self.structure.id,
                'name': self.structure.name,
                'entity_type': self.structure.entity_type
            }
        
        return {
            'id': self.id,
            'name': self.name,
            'search_query': self.search_query,
            'leads_allocated': self.leads_allocated,
            'leads_found': self.leads_found,
            'status': self.status,
            'task_id': self.task_id,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'structure': structure_data,
            'user_id': self.user_id
        }
        
    def get_active_task(self):
        """Get the active task for this job"""
        from core.job_details import get_task_for_job
        task_data = get_task_for_job(self)
        if task_data:
            return task_data['task']
        return None

class ScrapingTask(models.Model):
    """Task execution details for a scraping job"""
    job = models.ForeignKey(ScrapingJob, on_delete=models.CASCADE, related_name='core_tasks')
    task_id = models.CharField(max_length=255)  # Celery task ID or local task ID
    status = models.CharField(max_length=20, default='pending', 
                             choices=[
                                 ('pending', 'Pending'),
                                 ('initializing', 'Initializing'),
                                 ('running', 'Running'),
                                 ('paused', 'Paused'),
                                 ('completed', 'Completed'),
                                 ('failed', 'Failed'),
                                 ('stopped', 'Stopped')
                             ])
    current_step = models.CharField(max_length=100, blank=True, null=True)
    pages_explored = models.IntegerField(default=0)
    leads_found = models.IntegerField(default=0)
    unique_leads = models.IntegerField(default=0)
    start_time = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    completion_time = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"Task {self.task_id} for job {self.job.id}"
        
    def to_dict(self):
        """Convert task to dictionary format for API responses"""
        return {
            'id': self.task_id,
            'status': self.status,
            'current_step': self.current_step or 'Waiting to start...',
            'pages_explored': self.pages_explored,
            'leads_found': self.leads_found,
            'unique_leads': self.unique_leads,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'last_activity': self.last_activity.isoformat() if self.last_activity else None, 
            'completion_time': self.completion_time.isoformat() if self.completion_time else None,
            'error_message': self.error_message or '',
            'duration': (self.completion_time - self.start_time).total_seconds() if self.completion_time else (
                timezone.now() - self.start_time).total_seconds()
        }

class Lead(models.Model):
    """
    Model to represent leads extracted from scraping results, with additional tracking fields
    and customization options.
    """
    STATUS_CHOICES = [
        ('not_contacted', 'Non contacté'),
        ('contacted', 'Contacté'),
        ('interested', 'Intéressé'),
        ('not_interested', 'Pas intéressé'),
        ('converted', 'Converti'),
        ('rejected', 'Rejeté'),
    ]

    # Link to scraping results (one result can create multiple leads)
    scraping_result = models.ForeignKey('scraping.ScrapingResult', on_delete=models.SET_NULL, 
                                      null=True, related_name='leads')
    
    # Link to the user who owns this lead
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='leads')
    
    # Basic lead info
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    company = models.CharField(max_length=255, blank=True, null=True)
    position = models.CharField(max_length=255, blank=True, null=True)
    
    # Lead status and tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='not_contacted')
    source = models.CharField(max_length=100, blank=True, null=True)
    source_url = models.URLField(max_length=500, blank=True, null=True)
    
    # Lead data (json field for flexibility - stores the structure-specific data)
    data = models.JSONField(default=dict, blank=True)
    
    # Notes and custom fields
    notes = models.TextField(blank=True)
    priority = models.PositiveSmallIntegerField(default=0)  # Higher number = higher priority
    tags = models.JSONField(default=list, blank=True)  # List of tags
    
    # Flag to indicate if all required fields are present
    is_complete = models.BooleanField(default=True, help_text="Indicates if all required fields are present")
    missing_fields = models.JSONField(default=list, blank=True, help_text="List of missing required fields")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # If and when this lead was contacted
    last_contacted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Lead'
        verbose_name_plural = 'Leads'
    
    def __str__(self):
        completion_status = "✓" if self.is_complete else "✗"
        return f"{self.name} - {self.get_status_display()} [{completion_status}]"
    
    def mark_as_contacted(self):
        """Mark this lead as contacted and update the timestamp"""
        self.status = 'contacted'
        self.last_contacted_at = timezone.now()
        self.save(update_fields=['status', 'last_contacted_at', 'updated_at'])
    
    @property
    def days_since_created(self):
        """Return the number of days since this lead was created"""
        return (timezone.now() - self.created_at).days
    
    @property
    def days_since_contacted(self):
        """Return the number of days since this lead was last contacted"""
        if not self.last_contacted_at:
            return None
        return (timezone.now() - self.last_contacted_at).days
