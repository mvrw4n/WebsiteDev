# Guide d'Instruction pour le Projet Django Wizzy

## 1. Vue d'ensemble du Projet

Wizzy est une application web Django qui fournit une plateforme de scraping intelligent avec les fonctionnalités suivantes :
- Assistant IA conversationnel pour la détection et la création de structures de scraping
- Système de scraping automatisé avec gestion des tâches
- Système d'abonnement et de facturation intégré avec Stripe
- Interface utilisateur moderne et responsive

## 2. Architecture Technique

### 2.1 Backend (Django)
- Django 5.1+ avec REST framework
- Base de données PostgreSQL
- Système d'authentification personnalisé
- API RESTful pour toutes les fonctionnalités

### 2.2 Frontend
- JavaScript vanilla avec modules ES6
- Bootstrap 5 pour l'interface utilisateur
- Chart.js pour les visualisations
- Stripe.js pour les paiements

### 2.3 Structure des Applications Django

#### Core App
- Gestion des utilisateurs et des profils
- Système de chat IA
- Gestion des structures de scraping
- Vues principales et routage

#### Billing App
- Gestion des abonnements
- Intégration Stripe
- Gestion des plans et des quotas
- Système de facturation

#### Scraping App
- Gestion des tâches de scraping
- Système de logs et de résultats
- Contrôle des tâches (pause, reprise, arrêt)

## 3. Modèles de Données

### 3.1 Core Models
```python
class CustomUser(AbstractBaseUser):
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=False)
    stripe_customer_id = models.CharField(max_length=100)

class UserProfile(models.Model):
    user = models.OneToOneField(CustomUser)
    role = models.CharField(choices=ROLE_CHOICES)
    leads_quota = models.IntegerField()
    leads_used = models.IntegerField()
    unlimited_leads = models.BooleanField()

class Interaction(models.Model):
    user = models.ForeignKey(CustomUser)
    message = models.TextField()
    response = models.TextField()
    structure = models.JSONField()

class ScrapingStructure(models.Model):
    user = models.ForeignKey(CustomUser)
    name = models.CharField(max_length=100)
    entity_type = models.CharField(choices=ENTITY_TYPES)
    structure = models.JSONField()
```

### 3.2 Billing Models
```python
class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=100)
    stripe_price_id = models.CharField(max_length=100)
    price = models.DecimalField()
    interval = models.CharField(choices=INTERVAL_CHOICES)
    leads_quota = models.PositiveIntegerField()

class Subscription(models.Model):
    user = models.OneToOneField(CustomUser)
    plan = models.ForeignKey(SubscriptionPlan)
    stripe_subscription_id = models.CharField(max_length=100)
    status = models.CharField(choices=STATUS_CHOICES)
```

### 3.3 Scraping Models
```python
class ScrapingJob(models.Model):
    user = models.ForeignKey(CustomUser)
    structure = models.ForeignKey(ScrapingStructure)
    name = models.CharField(max_length=100)
    search_query = models.CharField(max_length=255)
    status = models.CharField(choices=STATUS_CHOICES)

class ScrapingTask(models.Model):
    job = models.ForeignKey(ScrapingJob)
    status = models.CharField(max_length=20)
    current_step = models.CharField(max_length=100)
    progress_percentage = models.IntegerField()
```

## 4. Système de Chat IA

### 4.1 Fonctionnalités
- Détection automatique de structures de scraping
- Gestion des actions asynchrones
- Historique des conversations
- Interface utilisateur en temps réel

### 4.2 Structure Frontend
```javascript
class ChatManager {
    constructor() {
        // Initialisation des éléments DOM
        // Gestion des événements
        // Système de messages
    }

    handleAIActions(actions) {
        // Traitement des actions IA
        // Affichage des structures
        // Gestion des états
    }

    renderMessages(messages) {
        // Rendu des messages
        // Gestion du scroll
        // Formatage du contenu
    }
}
```

## 5. Système de Scraping

### 5.1 Fonctionnalités
- Détection automatique de structures
- Gestion des tâches asynchrones
- Système de logs et de résultats
- Contrôle des tâches en cours

### 5.2 Types de Structures
- Mairies
- Entreprises
- B2B Leads
- Structures personnalisées

## 6. Système de Facturation

### 6.1 Fonctionnalités
- Plans d'abonnement
- Paiements Stripe
- Gestion des quotas
- Système de coupons

### 6.2 Plans Disponibles
- Wizzy Free
- Wizzy Classique
- Wizzy Premium
- Wizzy Lifetime

## 7. Bonnes Pratiques

### 7.1 Code
- Utiliser des docstrings pour toutes les classes et méthodes
- Suivre PEP 8 pour le style de code Python
- Commenter les sections complexes
- Utiliser des types hints quand possible

### 7.2 Sécurité
- Validation des données côté serveur
- Protection CSRF
- Authentification JWT
- Gestion sécurisée des paiements

### 7.3 Performance
- Optimisation des requêtes DB
- Mise en cache appropriée
- Gestion efficace des tâches asynchrones
- Optimisation des assets frontend

## 8. Workflow de Développement

### 8.1 Structure des Branches
- main: Production
- develop: Développement
- feature/*: Nouvelles fonctionnalités
- bugfix/*: Corrections de bugs
- release/*: Préparation des releases

### 8.2 Processus de Déploiement
1. Tests unitaires et d'intégration
2. Revue de code
3. Déploiement staging
4. Tests de production
5. Déploiement production

## 9. Points d'Attention

### 9.1 Performance
- Optimiser les requêtes DB
- Gérer efficacement les tâches asynchrones
- Minimiser les appels API
- Optimiser le chargement des assets

### 9.2 UX
- Feedback utilisateur immédiat
- Gestion des erreurs claire
- Interface responsive
- Animations fluides

### 9.3 Maintenance
- Logs détaillés
- Monitoring des performances
- Backups réguliers
- Documentation à jour

## 10. Extensions Futures

### 10.1 Fonctionnalités Planifiées
- API publique
- Intégrations tierces
- Analytics avancés
- Export de données

### 10.2 Améliorations Techniques
- Migration vers TypeScript
- Tests automatisés
- CI/CD amélioré
- Monitoring avancé 