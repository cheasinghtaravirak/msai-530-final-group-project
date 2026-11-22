from django.conf import settings
from django.db import connection
from django.http import JsonResponse


def health(request):
    """GET /health: 200 if the service and its database are reachable, 503 otherwise."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db = "ok"
    except Exception as exc:  # noqa: BLE001
        db = f"error: {exc.__class__.__name__}"
    ok = db == "ok"
    return JsonResponse(
        {"status": "ok" if ok else "degraded", "service": settings.SERVICE_NAME, "db": db},
        status=200 if ok else 503,
    )
