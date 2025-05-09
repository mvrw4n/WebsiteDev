"""
Settings package initialization.
"""

import os

# Default to development settings
DJANGO_ENV = os.environ.get('DJANGO_ENV', 'development')

if DJANGO_ENV == 'production':
    from .production import *
else:
    from .development import *

print(f"Using {DJANGO_ENV} settings...") 