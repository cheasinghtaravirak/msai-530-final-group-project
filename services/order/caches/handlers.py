from retail_common.consumer import handles

from .models import PriceCache, ProductCache


@handles("product.upserted")
def on_product_upserted(event: dict) -> None:
    p = event["payload"]
    if p["barcode"]:
        # A barcode moved to another SKU: free it first so the unique index holds whatever the event order.
        ProductCache.objects.filter(barcode=p["barcode"]).exclude(sku=p["sku"]).update(barcode=None)
    ProductCache.objects.update_or_create(
        sku=p["sku"], defaults={"barcode": p["barcode"], "name": p["name"], "active": p["status"] == "ACTIVE"}
    )


@handles("price.changed")
def on_price_changed(event: dict) -> None:
    p = event["payload"]
    PriceCache.objects.update_or_create(
        sku=p["sku"], branch_scope=p["branch_scope"], valid_from=p["valid_from"], defaults={"amount": p["amount"]}
    )
