from collections import defaultdict
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from retail_common.api import ApiError, Pagination
from retail_common.auth import BRANCH_MANAGER, CASHIER, HasRole, IsInternalService, require_branch_access
from retail_common.models import SKU_MAX_LENGTH

from .models import PaymentMethod, SalesOrder
from .orders import place_order, refund_order

SELLERS = (CASHIER, BRANCH_MANAGER)


class LineInput(serializers.Serializer):
    sku = serializers.CharField(max_length=SKU_MAX_LENGTH)
    qty = serializers.IntegerField(min_value=1, max_value=10_000)


class PaymentInput(serializers.Serializer):
    method = serializers.ChoiceField(choices=PaymentMethod.values)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))


class OrderInput(serializers.Serializer):
    order_id = serializers.UUIDField()
    branch_id = serializers.CharField(max_length=10)
    lines = LineInput(many=True, allow_empty=False, max_length=200)
    payments = PaymentInput(many=True)


class OrderListQuery(serializers.Serializer):
    branch_id = serializers.CharField(max_length=10)
    date = serializers.DateField(required=False)


class SummaryQuery(serializers.Serializer):
    date = serializers.DateField()


def local_iso(moment) -> str | None:
    return timezone.localtime(moment).isoformat(timespec="seconds") if moment else None


def order_data(order: SalesOrder) -> dict:
    return {
        "order_id": str(order.order_id),
        "branch_id": order.branch_id,
        "cashier_id": str(order.cashier_id),
        "status": order.status,
        "total_amount": f"{order.total_amount:.2f}",
        "completed_at": local_iso(order.completed_at),
        "sale_date": order.sale_date.isoformat(),
        "refunded_at": local_iso(order.refunded_at),
        "refund_date": order.refund_date.isoformat() if order.refund_date else None,
        "lines": [
            {
                "line_no": line.line_no,
                "sku": line.sku,
                "name": line.product_name_snapshot,
                "unit_price": f"{line.unit_price_snapshot:.2f}",
                "qty": line.qty,
                "line_total": f"{line.line_total:.2f}",
            }
            for line in order.lines.all()
        ],
        "payments": [{"method": p.method, "amount": f"{p.amount:.2f}"} for p in order.payments.all()],
    }


def get_order(request, order_id, *roles: str) -> SalesOrder:
    order = SalesOrder.objects.filter(pk=order_id).first()
    if order is None:
        raise ApiError("NOT_FOUND", "No such order", status=status.HTTP_404_NOT_FOUND)
    require_branch_access(request, order.branch_id, *roles)
    return order


class OrdersView(APIView):
    permission_classes = [HasRole(*SELLERS, branch_from="branch_id")]

    def post(self, request):
        body = OrderInput(data=request.data)
        body.is_valid(raise_exception=True)
        order, created = place_order(cashier_id=request.user.id, **body.validated_data)
        return Response(order_data(order), status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def get(self, request):
        query = OrderListQuery(data=request.query_params)
        query.is_valid(raise_exception=True)
        params = query.validated_data
        orders = SalesOrder.objects.filter(
            branch_id=params["branch_id"], sale_date=params.get("date") or timezone.localdate()
        ).prefetch_related("lines", "payments")
        paginator = Pagination()
        page = paginator.paginate_queryset(orders, request, view=self)
        return Response({"results": [order_data(o) for o in page], "count": paginator.page.paginator.count})


class OrderDetailView(APIView):
    permission_classes = [HasRole(*SELLERS)]

    def get(self, request, order_id):
        return Response(order_data(get_order(request, order_id, *SELLERS)))


class RefundView(APIView):
    permission_classes = [HasRole(BRANCH_MANAGER)]

    def post(self, request, order_id):
        get_order(request, order_id, BRANCH_MANAGER)
        return Response(order_data(refund_order(order_id, refunded_by=request.user.id)))


class SalesSummaryView(APIView):
    authentication_classes = []
    permission_classes = [IsInternalService]

    def get(self, request):
        query = SummaryQuery(data=request.query_params)
        query.is_valid(raise_exception=True)
        day = query.validated_data["date"]
        rows = defaultdict(lambda: {"order_count": 0, "total_amount": Decimal("0.00")})
        touched = SalesOrder.objects.filter(Q(sale_date=day) | Q(refund_date=day))
        for branch_id, total, sale_date, refund_date in touched.values_list(
            "branch_id", "total_amount", "sale_date", "refund_date"
        ):
            row = rows[branch_id]
            if sale_date == day:
                row["order_count"] += 1
                row["total_amount"] += total
            if refund_date == day:
                row["total_amount"] -= total
        return Response(
            [
                {
                    "branch_id": branch_id,
                    "order_count": row["order_count"],
                    "total_amount": f"{row['total_amount']:.2f}",
                }
                for branch_id, row in sorted(rows.items())
            ]
        )
