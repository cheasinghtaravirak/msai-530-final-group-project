from retail_common.consumer import handles

from .models import BranchRef, SkuRef


@handles("branch.upserted")
def on_branch_upserted(event: dict) -> None:
    p = event["payload"]
    BranchRef.objects.update_or_create(branch_id=p["branch_id"], defaults={"name": p["name"], "status": p["status"]})


@handles("product.upserted")
def on_product_upserted(event: dict) -> None:
    p = event["payload"]
    SkuRef.objects.update_or_create(
        sku=p["sku"],
        defaults={
            "name": p["name"],
            "category_id": p["category_id"],
            "pack_size": p["pack_size"],
            "active": p["status"] == "ACTIVE",
        },
    )
