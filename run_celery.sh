#!/bin/bash
# Script pour démarrer un worker Celery pour le projet Wizzy

# Vérifier les arguments
ENV=${1:-development}  # Utiliser development comme environnement par défaut si non spécifié

# Définir les variables d'environnement
export DJANGO_ENV="$ENV"
if [ "$ENV" = "production" ]; then
    export DJANGO_SETTINGS_MODULE="wizzydjango.settings.production"
else
    export DJANGO_SETTINGS_MODULE="wizzydjango.settings.development"
fi

# Vérifier si ce script est exécuté depuis le répertoire du projet
if [ ! -d "Wizzy" ] && [ ! -d "wizzydjango" ]; then
    echo "ERREUR: Ce script doit être exécuté depuis le répertoire racine du projet."
    echo "Veuillez vous placer dans le répertoire contenant les dossiers 'Wizzy' et 'wizzydjango'."
    exit 1
fi

# Message d'information
echo "======================================================"
echo "Démarrage d'un worker Celery pour le projet Wizzy"
echo "======================================================"
echo "Environnement: $ENV"
echo "DJANGO_SETTINGS_MODULE: $DJANGO_SETTINGS_MODULE"
echo "Dossier courant: $(pwd)"
echo ""

# Activer l'environnement virtuel si disponible
if [ -d "venv" ]; then
    echo "Activation de l'environnement virtuel..."
    source venv/bin/activate
elif [ -d "env" ]; then
    echo "Activation de l'environnement virtuel..."
    source env/bin/activate
elif [ -d "venvlinux" ]; then
    echo "Activation de l'environnement virtuel Linux..."
    source venvlinux/bin/activate
fi

# Vérifier si Celery est installé
if ! command -v celery &> /dev/null; then
    echo "ERREUR: Celery n'est pas installé. Veuillez l'installer avec:"
    echo "pip install celery redis"
    exit 1
fi

# Vérifier si Redis est disponible
echo "Vérification de la connexion Redis..."
if command -v redis-cli &> /dev/null; then
    if redis-cli ping | grep -q "PONG"; then
        echo "Redis est disponible ✓"
    else
        echo "AVERTISSEMENT: Redis ne répond pas. Assurez-vous que le serveur Redis est en cours d'exécution."
        echo "Essayez de démarrer Redis avec: sudo service redis-server start"
    fi
else
    echo "AVERTISSEMENT: La commande redis-cli n'est pas disponible. Impossible de vérifier Redis."
fi

# Démarrer Celery avec les options adaptées à l'environnement
echo "Démarrage du worker Celery pour l'environnement $ENV..."
echo "Logs détaillés activés. Appuyez sur Ctrl+C pour arrêter."
echo ""

# Options spécifiques selon l'environnement
if [ "$ENV" = "production" ]; then
    # En production, utilisez plus de workers et de sécurité
    celery -A wizzydjango worker -l info --concurrency=4 -Q celery,scraping,check
else
    # En développement, privilégiez la simplicité et le debugging
    echo "ASTUCE: Essayez de lancer 'celery -A wizzydjango worker -l info -Q celery' dans un autre terminal si vous avez des problèmes."
    celery -A wizzydjango worker -l debug --concurrency=2 -Q celery,scraping,check
fi 