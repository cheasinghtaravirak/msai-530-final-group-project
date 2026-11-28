from datetime import date

from django.db.models import Case, IntegerField, Value, When

from .models import PriceCache


def current_prices(skus, branch_id: str, on_date: date) -> dict[str, PriceCache]:
    rows = (
        PriceCache.objects.filter(
            sku__in=skus, branch_scope__in={branch_id, PriceCache.ALL_BRANCHES}, valid_from__lte=on_date
        )
        .annotate(
            scope_rank=Case(
                When(branch_scope=PriceCache.ALL_BRANCHES, then=Value(1)), default=Value(0), output_field=IntegerField()
            )
        )
        .order_by("sku", "scope_rank", "-valid_from")
        .distinct("sku")
    )
    return {p.sku: p for p in rows}
