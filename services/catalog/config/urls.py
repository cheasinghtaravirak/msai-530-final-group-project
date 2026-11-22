from django.urls import path

from retail_common.health import health

urlpatterns = [
    path("health", health),
]
