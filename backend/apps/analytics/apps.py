from django.apps import AppConfig


class AnalyticsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.analytics'
    label = 'analytics'

    def ready(self):
        """Connect to MongoDB Atlas when Django starts."""
        import os
        # Only connect in the main process, not during migrations or management checks
        if os.environ.get('RUN_MAIN') == 'true' or not os.environ.get('DJANGO_SETTINGS_MODULE'):
            return
        try:
            from services.mongodb_service import MongoDBService
            svc = MongoDBService()
            if not svc._connected:
                svc.connect()
        except Exception:
            pass  # Logged inside connect()
