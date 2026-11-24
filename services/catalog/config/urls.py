from django.urls import include, path

from retail_common.health import health

urlpatterns = [
    path("health", health),
    path("", include("products.urls")),
]
