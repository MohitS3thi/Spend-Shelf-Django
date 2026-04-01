import os

from django.core.wsgi import get_wsgi_application

# Compatibility entrypoint for platforms configured with: gunicorn app:app
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "expense_tracker.settings")

app = get_wsgi_application()
