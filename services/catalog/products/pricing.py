from datetime import date

from django.db.models import Case, IntegerField, Value, When

from .models import ALL_BRANCHES, Price


def current_prices(skus, branch_id: str, on_date: date) -> dict[str, Price]:
    """The price rule (design doc §5.2), per SKU: the latest valid_from <= on_date for the branch,
    else the latest for ALL. SKUs with no price are missing from the result."""
    rows = (
        Price.objects.filter(sku_id__in=skus, branch_scope__in={branch_id, ALL_BRANCHES}, valid_from__lte=on_date)
        .annotate(
            scope_rank=Case(
                When(branch_scope=ALL_BRANCHES, then=Value(1)), default=Value(0), output_field=IntegerField()
            )
        )
        .order_by("sku_id", "scope_rank", "-valid_from")
        .distinct("sku_id")
    )
    return {p.sku_id: p for p in rows}
