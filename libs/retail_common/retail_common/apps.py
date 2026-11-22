from django.apps import AppConfig


class RetailCommonConfig(AppConfig):
    name = "retail_common"
    label = "retail_common"
    default_auto_field = "django.db.models.BigAutoField"
    verbose_name = "Retail common (outbox, processed events)"
