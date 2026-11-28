from retail_common.consumer import handles

from .models import PriceCache, ProductCache


def release_barcode(barcode: str, keep_sku: str) -> None:
    ProductCache.objects.filter(barcode=barcode).exclude(sku=keep_sku).update(barcode=None)


@handles("product.upserted")
def on_product_upserted(event: dict) -> None:
    p = event["payload"]
    if p["barcode"]:
        release_barcode(p["barcode"], keep_sku=p["sku"])
    ProductCache.objects.update_or_create(
        sku=p["sku"], defaults={"barcode": p["barcode"], "name": p["name"], "active": p["status"] == "ACTIVE"}
    )


@handles("price.changed")
def on_price_changed(event: dict) -> None:
    p = event["payload"]
    PriceCache.objects.update_or_create(
        sku=p["sku"], branch_scope=p["branch_scope"], valid_from=p["valid_from"], defaults={"amount": p["amount"]}
    )
