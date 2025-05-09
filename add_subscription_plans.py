#!/usr/bin/env python
"""
Script pour ajouter les plans d'abonnement Wizzy dans la base de données.
Exécuter avec: python add_subscription_plans.py
"""

import os
import sys
import django

# Configurer l'environnement Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wizzydjango.settings.development')
django.setup()

# Importer le modèle après avoir configuré l'environnement
from billing.models import SubscriptionPlan
from django.db import transaction

def create_subscription_plans():
    """Créer les plans d'abonnement standard pour Wizzy"""
    print('Création des plans d\'abonnement...')
    
    with transaction.atomic():
        # Vérifier si des plans existent déjà
        if SubscriptionPlan.objects.exists():
            print('Les plans d\'abonnement existent déjà. Annulation de la création.')
            return
        
        # Créer les plans basés sur nos besoins UI
        plans = [
            {
                'name': 'Wizzy Free',
                'stripe_price_id': 'price_free_placeholder',
                'price': 0,
                'interval': 'month',
                'leads_quota': 5,
                'features': [
                    'Scraping de haute qualité limité',
                    'Maximum d\'informations',
                    'Prompts personnalisés pour approcher les clients',
                    'Conseils personnalisés spécifiques à votre service/bien',
                    'IA qui parle'
                ]
            },
            {
                'name': 'Wizzy Classique',
                'stripe_price_id': 'price_classic_placeholder',
                'price': 80,
                'interval': 'month',
                'leads_quota': 100,
                'features': [
                    'Scraping illimité (100/jour)',
                    'Maximum d\'informations',
                    'Automatisation des messages personnalisés',
                    'Scraping de haute qualité sur tous les sites y compris les réseaux sociaux',
                    'Prompts personnalisés pour approcher les clients',
                    'Conseils personnalisés spécifiques à votre service/bien',
                    'Possibilité de discuter avec l\'IA librement, IA qui parle'
                ]
            },
            {
                'name': 'Wizzy Premium Closing',
                'stripe_price_id': 'price_premium_closing_placeholder',
                'price': 170,
                'interval': 'month',
                'leads_quota': 150,
                'features': [
                    'Scraping illimité (150/jour)',
                    'Maximum d\'informations',
                    'Automatisation des messages personnalisés',
                    'Scraping de haute qualité sur tous les sites y compris les réseaux sociaux',
                    'Prompts personnalisés pour approcher les clients',
                    'Conseils personnalisés spécifiques à votre service/bien',
                    'Possibilité de discuter avec l\'IA librement, IA qui parle',
                    'Équipe de chez Closer qui va se charger de closer à votre place en contre partie d\'un pourcentage'
                ]
            },
            {
                'name': 'Wizzy Premium Scaling',
                'stripe_price_id': 'price_premium_scaling_placeholder',
                'price': 300,
                'interval': 'month',
                'leads_quota': 150,
                'features': [
                    'Scraping illimité (150/jour)',
                    'Maximum d\'informations',
                    'Automatisation des messages personnalisés',
                    'Scraping de haute qualité sur tous les sites y compris les réseaux sociaux',
                    'Prompts personnalisés pour approcher les clients',
                    'Conseils personnalisés spécifiques à votre service/bien',
                    'Possibilité de discuter avec l\'IA librement, IA qui parle',
                    'Équipe de chez Mathis Clout qui va se charger de scaler votre business en contre partie d\'un pourcentage mensuel'
                ]
            }
        ]
        
        # Créer les plans dans la base de données
        for plan_data in plans:
            features_list = plan_data.pop('features')
            # Convertir la liste de fonctionnalités en dictionnaire numéroté pour le champ JSONField
            plan_data['features'] = {str(i): feature for i, feature in enumerate(features_list)}
            SubscriptionPlan.objects.create(**plan_data)
            print(f'✓ Plan créé: {plan_data["name"]}')
            
        print(f'Création réussie des {len(plans)} plans d\'abonnement!')

if __name__ == "__main__":
    create_subscription_plans() 