import uuid

from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from refs.models import SkuRef
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from retail_common.api import ApiError, Pagination
from retail_common.auth import BRANCH_MANAGER, HasRole
from retail_common.models import SKU_MAX_LENGTH

from .ledger import Cause, move_stock
from .models import MovementReason, StockLevel, StockMovement


def local_iso(moment) -> str:
    return timezone.localtime(moment).isoformat(timespec="seconds")


def stock_rows(levels) -> list[dict]:
    names = dict(SkuRef.objects.filter(sku__in=[level.sku for level in levels]).values_list("sku", "name"))
    return [
        {
            "sku": level.sku,
            "name": names.get(level.sku, ""),
            "on_hand": level.on_hand,
            "on_order": level.on_order,
            "low": level.on_hand <= settings.LOW_STOCK_THRESHOLD,
        }
        for level in levels
    ]


def require_known_skus(skus) -> None:
    unknown = set(skus) - set(SkuRef.objects.filter(sku__in=skus).values_list("sku", flat=True))
    if unknown:
        raise ApiError(
            "UNKNOWN_SKU",
            "Inventory does not know these SKUs",
            status=status.HTTP_404_NOT_FOUND,
            details={"skus": sorted(unknown)},
        )


def paginated(request, view, queryset, to_rows) -> Response:
    paginator = Pagination()
    page = paginator.paginate_queryset(queryset, request, view=view)
    return Response({"results": to_rows(page), "count": paginator.page.paginator.count})


class StockQuery(serializers.Serializer):
    branch_id = serializers.CharField(max_length=10)
    sku = serializers.CharField(max_length=SKU_MAX_LENGTH, required=False)
    q = serializers.CharField(max_length=100, required=False)
    low_only = serializers.BooleanField(default=False)
    negative_only = serializers.BooleanField(default=False)


class StockView(APIView):
    permission_classes = [HasRole(BRANCH_MANAGER, branch_from="branch_id")]

    def get(self, request):
        query = StockQuery(data=request.query_params)
        query.is_valid(raise_exception=True)
        params = query.validated_data
        levels = StockLevel.objects.filter(branch_id=params["branch_id"])
        if "sku" in params:
            levels = levels.filter(sku=params["sku"])
        if q := params.get("q"):
            named = SkuRef.objects.filter(name__icontains=q).values("sku")
            levels = levels.filter(Q(sku__icontains=q) | Q(sku__in=named))
        if params["low_only"]:
            levels = levels.filter(on_hand__lte=settings.LOW_STOCK_THRESHOLD)
        if params["negative_only"]:
            levels = levels.filter(on_hand__lt=0)
        return paginated(request, self, levels, stock_rows)


def movement_rows(movements) -> list[dict]:
    return [
        {
            "movement_id": str(m.movement_id),
            "qty_delta": m.qty_delta,
            "reason": m.reason,
            "source_ref": m.source_ref,
            "source_line": m.source_line,
            "note": m.note,
            "created_by": str(m.created_by) if m.created_by else None,
            "occurred_at": local_iso(m.occurred_at),
        }
        for m in movements
    ]


class MovementsView(APIView):
    permission_classes = [HasRole(BRANCH_MANAGER, branch_from="branch_id")]

    def get(self, request, branch_id, sku):
        movements = StockMovement.objects.filter(branch_id=branch_id, sku=sku).order_by("-occurred_at", "-source_line")
        return paginated(request, self, movements, movement_rows)


class AdjustmentInput(serializers.Serializer):
    branch_id = serializers.CharField(max_length=10)
    sku = serializers.CharField(max_length=SKU_MAX_LENGTH)
    qty_delta = serializers.IntegerField(min_value=-100_000, max_value=100_000)
    note = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")

    def validate_qty_delta(self, value: int) -> int:
        if value == 0:
            raise serializers.ValidationError("Must not be zero.")
        return value


class AdjustmentsView(APIView):
    permission_classes = [HasRole(BRANCH_MANAGER, branch_from="branch_id")]

    def post(self, request):
        body = AdjustmentInput(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        require_known_skus([data["sku"]])
        level = move_stock(
            data["branch_id"],
            data["sku"],
            data["qty_delta"],
            Cause(MovementReason.ADJUST, str(uuid.uuid4()), 1),
            timezone.localtime(),
            note=data["note"],
            created_by=request.user.id,
        )
        return Response(stock_rows([level])[0], status=status.HTTP_201_CREATED)
