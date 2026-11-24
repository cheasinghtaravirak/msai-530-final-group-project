from datetime import datetime

from retail_common.consumer import handles

from .models import SupplierTerms


@handles("supplier_terms.changed")
def on_supplier_terms_changed(event: dict) -> None:
    """Keep only the preferred supplier's terms per SKU (one row per SKU).

    Events for different suppliers sit on different partitions, so a promotion can arrive before
    an older one, and a demotion before the promotion that replaced it. A demotion deletes the
    row only if it is still that supplier's, and an older promotion never overwrites a newer one.
    """
    p = event["payload"]
    if not p["is_preferred"]:
        SupplierTerms.objects.filter(sku=p["sku"], supplier_id=p["supplier_id"]).delete()
        return
    occurred_at = datetime.fromisoformat(event["occurred_at"])
    current = SupplierTerms.objects.select_for_update().filter(sku=p["sku"]).first()
    if current and current.occurred_at and current.occurred_at > occurred_at:
        return
    SupplierTerms.objects.update_or_create(
        sku=p["sku"],
        defaults={
            "supplier_id": p["supplier_id"],
            "lead_time_days": p["lead_time_days"],
            "pack_size": p["pack_size"],
            "min_order_qty": p["min_order_qty"],
            "occurred_at": occurred_at,
        },
    )
