from retail_common.events import publish_event

from .models import Price, Sku, SupplierSku

CURRENCY = "USD"


def publish_sku(sku: Sku) -> None:
    product = sku.product
    publish_event(
        "product.upserted",
        {
            "sku": sku.sku,
            "product_id": product.product_id,
            "barcode": sku.barcode,
            "name": sku.name,
            "brand": product.brand,
            "category_id": product.category_id,
            "category_name": product.category.name,
            "pack_size": sku.pack_size,
            "status": product.status,
        },
        key=sku.sku,
    )
    for terms in sku.supplier_terms.select_related("supplier"):
        publish_terms(terms)


def publish_price(price: Price) -> None:
    publish_event(
        "price.changed",
        {
            "sku": price.sku_id,
            "branch_scope": price.branch_scope,
            "amount": price.amount,
            "currency": CURRENCY,
            "valid_from": price.valid_from,
        },
        key=f"{price.sku_id}:{price.branch_scope}:{price.valid_from.isoformat()}",
    )


def publish_terms(terms: SupplierSku) -> None:
    publish_event(
        "supplier_terms.changed",
        {
            "sku": terms.sku_id,
            "supplier_id": terms.supplier_id,
            "is_preferred": terms.is_preferred,
            "lead_time_days": terms.supplier.lead_time_days,
            "pack_size": terms.sku.pack_size,
            "min_order_qty": terms.min_order_qty,
            "unit_cost": terms.unit_cost,
        },
        key=f"{terms.supplier_id}:{terms.sku_id}",
    )
