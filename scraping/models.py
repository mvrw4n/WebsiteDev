from django.db import models
from django.conf import settings
from core.models import ScrapingJob, ScrapingStructure

class ScrapingTask(models.Model):
    """
    Représente une tâche de scraping en cours d'exécution
    """
    STATUS_CHOICES = [
        ('initializing', 'Initialisation'),
        ('crawling', 'Exploration'),
        ('extracting', 'Extraction de données'),
        ('processing', 'Traitement'),
        ('paused', 'En pause'),
        ('completed', 'Terminé'),
        ('failed', 'Échoué'),
    ]

    job = models.ForeignKey(ScrapingJob, on_delete=models.CASCADE, related_name='scraping_tasks')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='initializing')
    current_step = models.CharField(max_length=255, blank=True, null=True)
    pages_explored = models.IntegerField(default=0)
    leads_found = models.IntegerField(default=0)
    unique_leads = models.IntegerField(default=0)
    duplicate_leads = models.IntegerField(default=0)
    rate_limited_leads = models.IntegerField(default=0, help_text="Leads non créés car l'utilisateur a atteint sa limite")
    incomplete_leads = models.IntegerField(default=0, help_text="Leads non créés car des champs obligatoires étaient manquants")
    start_time = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    completion_time = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, null=True)
    task_data = models.JSONField(default=dict, blank=True, null=True)
    celery_task_id = models.CharField(max_length=255, blank=True, null=True)
    
    class Meta:
        ordering = ['-start_time']
        
    def __str__(self):
        return f"Task for {self.job.name} - {self.status}"
        
    @property
    def duration(self):
        """Calculate task duration in seconds"""
        if self.completion_time:
            return (self.completion_time - self.start_time).total_seconds()
        return (self.last_activity - self.start_time).total_seconds()
        
    @property
    def progress_percentage(self):
        """Calculate approx. progress percentage based on leads found vs allocated"""
        if self.status == 'completed':
            return 100
        
        if self.job.leads_allocated:
            return min(round((self.leads_found / self.job.leads_allocated) * 100), 99)
        return 0

class ScrapingLog(models.Model):
    """
    Journal détaillé de l'exécution d'une tâche de scraping
    """
    LOG_TYPES = [
        ('info', 'Information'),
        ('warning', 'Avertissement'),
        ('error', 'Erreur'),
        ('success', 'Succès'),
        ('action', 'Action'),
    ]
    
    task = models.ForeignKey(ScrapingTask, on_delete=models.CASCADE, related_name='logs')
    timestamp = models.DateTimeField(auto_now_add=True)
    log_type = models.CharField(max_length=10, choices=LOG_TYPES, default='info')
    message = models.TextField()
    details = models.JSONField(null=True, blank=True)
    
    class Meta:
        ordering = ['timestamp']
        
    def __str__(self):
        return f"{self.get_log_type_display()}: {self.message[:50]}"

class ScrapingResult(models.Model):
    """
    Stocke les résultats de leads trouvés lors d'une tâche de scraping
    """
    task = models.ForeignKey(ScrapingTask, on_delete=models.CASCADE, related_name='results')
    lead_data = models.JSONField()
    source_url = models.URLField(max_length=500, blank=True, null=True)
    is_processed = models.BooleanField(default=False)
    is_duplicate = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        if 'nom' in self.lead_data:
            return f"Lead: {self.lead_data.get('nom', 'Sans nom')}"
        return f"Lead #{self.id}"

class LeadEnrichment(models.Model):
    """
    Stocke les données d'enrichissement pour les leads trouvés
    Ces données seront utilisées par l'IA pour personnaliser les conversations
    """
    lead = models.OneToOneField(ScrapingResult, on_delete=models.CASCADE, related_name='enrichment')
    interests = models.CharField(max_length=255, blank=True, null=True, help_text="Centres d'intérêt du lead")
    budget = models.CharField(max_length=100, blank=True, null=True, help_text="Budget approximatif du lead")
    preferences = models.CharField(max_length=255, blank=True, null=True, help_text="Préférences de contact ou de produit")
    purchase_history = models.CharField(max_length=255, blank=True, null=True, help_text="Historique d'achat ou d'interaction")
    additional_info = models.TextField(blank=True, null=True, help_text="Informations supplémentaires pour personnaliser l'approche")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        lead_name = "N/A"
        if 'nom' in self.lead.lead_data:
            lead_name = self.lead.lead_data.get('nom')
        return f"Enrichissement pour {lead_name}"
    
    @property
    def is_enriched(self):
        """
        Détermine si ce lead a été enrichi de manière significative
        """
        # Considéré comme enrichi si au moins un champ est rempli
        return (
            self.interests or
            self.budget or
            self.preferences or
            self.purchase_history or
            self.additional_info
        )

class TaskQueue(models.Model):
    """
    File d'attente pour les tâches de scraping
    """
    PRIORITY_CHOICES = [
        (1, 'Haute'),
        (2, 'Normale'),
        (3, 'Basse'),
    ]
    
    job = models.ForeignKey(ScrapingJob, on_delete=models.CASCADE, related_name='queue_entries')
    priority = models.IntegerField(choices=PRIORITY_CHOICES, default=2)
    scheduled_time = models.DateTimeField(null=True, blank=True)
    is_processed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['priority', 'created_at']
        
    def __str__(self):
        return f"Queue entry for {self.job.name} - Priority: {self.get_priority_display()}"

class ScrapedSite(models.Model):
    """
    Tracks sites that have been scraped to avoid duplicates and manage rate limits
    """
    url = models.URLField(max_length=500)
    domain = models.CharField(max_length=255)
    last_scraped = models.DateTimeField(auto_now=True)
    scraping_count = models.IntegerField(default=0)
    success_rate = models.FloatField(default=0.0)
    last_error = models.TextField(blank=True, null=True)
    rate_limit_until = models.DateTimeField(null=True, blank=True)
    structure = models.ForeignKey('core.ScrapingStructure', on_delete=models.CASCADE, related_name='scraped_sites')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['url', 'structure']
        indexes = [
            models.Index(fields=['domain', 'structure']),
            models.Index(fields=['last_scraped']),
            models.Index(fields=['rate_limit_until']),
        ]

    def __str__(self):
        return f"{self.domain} - {self.structure.name}"

    def update_scraping_stats(self, success=True, error=None):
        """Update scraping statistics for this site"""
        self.scraping_count += 1
        if success:
            self.success_rate = ((self.success_rate * (self.scraping_count - 1)) + 1) / self.scraping_count
        else:
            self.success_rate = (self.success_rate * (self.scraping_count - 1)) / self.scraping_count
            self.last_error = error
        self.save()

    def set_rate_limit(self, minutes=60):
        """Set rate limit for this site"""
        from django.utils import timezone
        self.rate_limit_until = timezone.now() + timezone.timedelta(minutes=minutes)
        self.save()

    @property
    def is_rate_limited(self):
        """Check if site is currently rate limited"""
        if not self.rate_limit_until:
            return False
        from django.utils import timezone
        return timezone.now() < self.rate_limit_until

    @property
    def can_scrape(self):
        """Check if site can be scraped based on rate limits and success rate"""
        if self.is_rate_limited:
            return False
        return self.success_rate >= 0.5  # Only scrape sites with at least 50% success rate

class CeleryWorkerActivity(models.Model):
    """
    Tracks the real-time activity of Celery workers for a user-friendly monitoring dashboard
    """
    ACTIVITY_TYPES = [
        ('scraping', 'Scraping Web Pages'),
        ('serp_search', 'Performing SERP Search'),
        ('extracting', 'Extracting Data'),
        ('processing', 'Processing Results'),
        ('analyzing', 'Analyzing Content'),
        ('waiting', 'Waiting for Next Task'),
        ('idle', 'Idle'),
    ]
    
    STATUS_CHOICES = [
        ('running', 'Running'),
        ('idle', 'Idle'),
        ('error', 'Error'),
    ]
    
    worker_name = models.CharField(max_length=255)
    hostname = models.CharField(max_length=255)
    task = models.ForeignKey(ScrapingTask, on_delete=models.SET_NULL, null=True, related_name='worker_activities')
    activity_type = models.CharField(max_length=50, choices=ACTIVITY_TYPES, default='idle')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='idle')
    current_url = models.URLField(max_length=500, blank=True, null=True)
    details = models.JSONField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name_plural = 'Celery worker activities'
    
    def __str__(self):
        return f"{self.worker_name} - {self.activity_type} ({self.status})"
