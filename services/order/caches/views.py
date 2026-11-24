from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from retail_common.api import ApiError, Pagination
from retail_common.auth import BRANCH_MANAGER, CASHIER, HasRole

from .models import ProductCache
from .pricing import current_prices


class PosItemQuery(serializers.Serializer):
    branch_id = serializers.CharField(max_length=10)
    barcode = serializers.CharField(max_length=50, required=False)
    q = serializers.CharField(max_length=100, required=False)

    def validate(self, attrs):
        if ("barcode" in attrs) == ("q" in attrs):
            raise serializers.ValidationError("Send exactly one of barcode or q")
        return attrs


def items_data(products, branch_id: str) -> list[dict]:
    prices = current_prices([p.sku for p in products], branch_id, timezone.localdate())
    return [
        {
            "sku": p.sku,
            "name": p.name,
            "unit_price": f"{prices[p.sku].amount:.2f}" if p.sku in prices else None,
        }
        for p in products
    ]


class PosItemsView(APIView):
    """GET /pos/items?branch_id=&barcode= | &q= : sellable items from the local copies, priced by the §5.2 rule."""

    permission_classes = [HasRole(CASHIER, BRANCH_MANAGER, branch_from="branch_id")]

    def get(self, request):
        query = PosItemQuery(data=request.query_params)
        query.is_valid(raise_exception=True)
        params = query.validated_data
        active = ProductCache.objects.filter(active=True)

        if "barcode" in params:
            product = active.filter(barcode=params["barcode"]).first()
            if product is None:
                raise ApiError(
                    "ITEM_NOT_FOUND", f"No item with barcode {params['barcode']}", status=status.HTTP_404_NOT_FOUND
                )
            return Response(items_data([product], params["branch_id"])[0])

        q = params["q"]
        matches = active.filter(Q(name__icontains=q) | Q(sku__icontains=q) | Q(barcode=q))
        paginator = Pagination()
        page = paginator.paginate_queryset(matches, request, view=self)
        return Response({"results": items_data(page, params["branch_id"]), "count": paginator.page.paginator.count})
