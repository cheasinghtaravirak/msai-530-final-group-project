from datetime import datetime

from retail_common.consumer import handles

from .models import SupplierTerms


@handles("supplier_terms.changed")
def on_supplier_terms_changed(event: dict) -> None:
    # The topic key is supplier_id:sku (design doc §6.4), so two suppliers' events for one SKU can
    # arrive out of order. A demotion only deletes its own row, and an older promotion never wins.
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
