"""
WSGI config for wizzydjango project.
"""

import os
import sys

# Ajoutez le chemin du projet aux chemins de recherche Python si nécessaire
path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if path not in sys.path:
    sys.path.append(path)

# Définir le module de paramètres
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wizzydjango.settings.production')
os.environ.setdefault('USE_SQLITE', 'True')

# Importer get_wsgi_application après avoir défini DJANGO_SETTINGS_MODULE
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
