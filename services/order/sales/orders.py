"""The order lifecycle: COMPLETED on creation, then REFUNDED at most once.

Each transition saves the order and its outbox event in one transaction, and repeating either
one returns the stored order without a second event.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from urllib.parse import quote
from uuid import UUID
from zoneinfo import ZoneInfo

import httpx
from caches.models import BranchRef, ProductCache
from caches.pricing import current_prices
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import status

from retail_common.api import ApiError
from retail_common.context import get_request_id
from retail_common.events import publish_event

from .models import OrderLine, OrderStatus, Payment, SalesOrder

S6_TIMEOUT_SECONDS = 0.3


@dataclass(frozen=True)
class PricedLine:
    sku: str
    name: str
    unit_price: Decimal
    qty: int

    @property
    def line_total(self) -> Decimal:
        return self.unit_price * self.qty


def local_date(branch_id: str, moment: datetime) -> date:
    branch = BranchRef.objects.filter(pk=branch_id).first()
    return moment.astimezone(ZoneInfo(branch.timezone) if branch else timezone.get_current_timezone()).date()


def catalog_price(sku: str, branch_id: str) -> tuple[str, Decimal]:
    """S6: ask Catalog for a SKU missing from the caches."""
    try:
        response = httpx.get(
            f"{settings.CATALOG_URL}/prices/{quote(sku, safe='')}",
            params={"branch_id": branch_id},
            headers={"X-Service-Token": settings.SERVICE_TOKEN, "X-Request-ID": get_request_id() or ""},
            timeout=S6_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        body = response.json()
        return body["name"], Decimal(body["amount"])
    except (httpx.HTTPError, KeyError, ValueError, ArithmeticError) as exc:
        raise ApiError(
            "PRICE_UNAVAILABLE",
            f"No price available for {sku}",
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"sku": sku},
        ) from exc


def price_lines(branch_id: str, lines: list[dict], on_date: date) -> list[PricedLine]:
    skus = {line["sku"] for line in lines}
    products = ProductCache.objects.in_bulk(skus)
    prices = current_prices(skus, branch_id, on_date)
    priced = []
    for line in lines:
        sku = line["sku"]
        product = products.get(sku)
        if product and not product.active:
            raise ApiError(
                "ITEM_NOT_FOUND",
                f"{sku} is no longer sold",
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                details={"sku": sku},
            )
        if product and sku in prices:
            name, unit_price = product.name, prices[sku].amount
        else:
            name, unit_price = catalog_price(sku, branch_id)
        priced.append(PricedLine(sku, name, unit_price, line["qty"]))
    return priced


def stored_order(order_id: UUID, branch_id: str) -> SalesOrder | None:
    order = SalesOrder.objects.filter(pk=order_id).first()
    if order and order.branch_id != branch_id:
        raise ApiError("ORDER_ID_CONFLICT", "This order_id belongs to another branch", status=status.HTTP_409_CONFLICT)
    return order


def place_order(
    *, order_id: UUID, branch_id: str, cashier_id: str, lines: list[dict], payments: list[dict]
) -> tuple[SalesOrder, bool]:
    """Returns the order and whether this call created it."""
    if existing := stored_order(order_id, branch_id):
        return existing, False
    if BranchRef.objects.filter(pk=branch_id, status=BranchRef.CLOSED).exists():
        raise ApiError("BRANCH_CLOSED", f"Branch {branch_id} is closed", status=status.HTTP_409_CONFLICT)

    now = timezone.now()
    sale_date = local_date(branch_id, now)
    # Priced before the transaction opens: S6 is a network call.
    priced = price_lines(branch_id, lines, sale_date)
    total = sum((line.line_total for line in priced), Decimal("0.00"))
    if sum(payment["amount"] for payment in payments) != total:
        raise ApiError(
            "PAYMENT_MISMATCH",
            f"Payments must add up to {total}",
            details={
                "total_amount": f"{total:.2f}",
                "lines": [{"sku": line.sku, "unit_price": f"{line.unit_price:.2f}"} for line in priced],
            },
        )

    try:
        with transaction.atomic():
            order = SalesOrder.objects.create(
                order_id=order_id,
                branch_id=branch_id,
                cashier_id=cashier_id,
                total_amount=total,
                completed_at=now,
                sale_date=sale_date,
            )
            OrderLine.objects.bulk_create(
                OrderLine(
                    order=order,
                    line_no=line_no,
                    sku=line.sku,
                    product_name_snapshot=line.name,
                    unit_price_snapshot=line.unit_price,
                    qty=line.qty,
                    line_total=line.line_total,
                )
                for line_no, line in enumerate(priced, start=1)
            )
            Payment.objects.bulk_create(Payment(order=order, **payment) for payment in payments)
            publish_event(
                "order.completed",
                {
                    "order_id": order_id,
                    "branch_id": branch_id,
                    "channel": order.channel,
                    "cashier_id": cashier_id,
                    "completed_at": timezone.localtime(now),
                    "sale_date": sale_date,
                    "total_amount": total,
                    "lines": [
                        {
                            "line_no": line_no,
                            "sku": line.sku,
                            "qty": line.qty,
                            "unit_price": line.unit_price,
                            "line_total": line.line_total,
                        }
                        for line_no, line in enumerate(priced, start=1)
                    ],
                },
                key=str(order_id),
            )
    except IntegrityError:
        # A concurrent request with the same order_id won the insert.
        existing = stored_order(order_id, branch_id)
        if existing is None:
            raise
        return existing, False
    return order, True


def refund_order(order_id: UUID, refunded_by: str) -> SalesOrder:
    with transaction.atomic():
        order = SalesOrder.objects.select_for_update().get(pk=order_id)
        if order.status == OrderStatus.REFUNDED:
            return order
        now = timezone.now()
        order.status = OrderStatus.REFUNDED
        order.refunded_at = now
        order.refund_date = local_date(order.branch_id, now)
        order.refunded_by = refunded_by
        order.save(update_fields=["status", "refunded_at", "refund_date", "refunded_by"])
        publish_event(
            "order.refunded",
            {
                "order_id": order.order_id,
                "branch_id": order.branch_id,
                "channel": order.channel,
                "refunded_at": timezone.localtime(now),
                "refund_date": order.refund_date,
                "lines": [
                    {"line_no": line.line_no, "sku": line.sku, "qty": line.qty, "line_total": line.line_total}
                    for line in order.lines.all()
                ],
            },
            key=str(order.order_id),
        )
    return order
