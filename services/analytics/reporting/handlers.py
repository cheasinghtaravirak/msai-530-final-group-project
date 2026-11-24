from retail_common.consumer import handles

from .models import DimBranch, DimProduct


@handles("branch.upserted")
def on_branch_upserted(event: dict) -> None:
    p = event["payload"]
    DimBranch.objects.update_or_create(
        branch_id=p["branch_id"],
        defaults={"name": p["name"], "region": p["region"], "status": p["status"]},
    )


@handles("product.upserted")
def on_product_upserted(event: dict) -> None:
    p = event["payload"]
    DimProduct.objects.update_or_create(
        sku=p["sku"],
        defaults={
            "name": p["name"],
            "category_id": p["category_id"],
            "category_name": p["category_name"],
            "brand": p["brand"],
        },
    )
