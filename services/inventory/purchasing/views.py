from django.db import transaction
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView
from stock.ledger import Cause, move_stock
from stock.models import MovementReason
from stock.views import local_iso, require_known_skus

from retail_common.api import ApiError
from retail_common.auth import BRANCH_MANAGER, HasRole

from .models import GoodsReceipt, ReceiptLine


class ReceiptLineInput(serializers.Serializer):
    sku = serializers.CharField(max_length=50)
    qty = serializers.IntegerField(min_value=1, max_value=100_000)


class ReceiptInput(serializers.Serializer):
    po_id = serializers.UUIDField(required=False, allow_null=True)
    branch_id = serializers.CharField(max_length=10)
    lines = ReceiptLineInput(many=True, allow_empty=False, max_length=500)

    def validate_lines(self, lines: list[dict]) -> list[dict]:
        if len({line["sku"] for line in lines}) != len(lines):
            raise serializers.ValidationError("A SKU may appear on one line only.")
        return lines


class ReceiptsView(APIView):
    permission_classes = [HasRole(BRANCH_MANAGER, branch_from="branch_id")]

    def post(self, request):
        body = ReceiptInput(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        if data.get("po_id"):
            raise ApiError("VALIDATION_ERROR", "Receipts against a purchase order arrive in Phase 4")
        require_known_skus([line["sku"] for line in data["lines"]])
        now = timezone.localtime()
        with transaction.atomic():
            receipt = GoodsReceipt.objects.create(
                branch_id=data["branch_id"], received_by=request.user.id, received_at=now
            )
            ReceiptLine.objects.bulk_create(ReceiptLine(receipt=receipt, **line) for line in data["lines"])
            for position, line in enumerate(data["lines"], start=1):
                cause = Cause(MovementReason.RECEIPT, str(receipt.receipt_id), position)
                move_stock(data["branch_id"], line["sku"], line["qty"], cause, now, created_by=request.user.id)
        return Response(
            {
                "receipt_id": str(receipt.receipt_id),
                "po_id": None,
                "branch_id": receipt.branch_id,
                "received_by": str(receipt.received_by),
                "received_at": local_iso(now),
                "lines": data["lines"],
            },
            status=status.HTTP_201_CREATED,
        )
