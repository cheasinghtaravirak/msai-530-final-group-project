from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from retail_common.api import ApiError, Pagination
from retail_common.auth import BRANCH_MANAGER, CASHIER, HQ_ADMIN, HasRole, IsInternalService

from .events import publish_price, publish_sku, publish_terms
from .models import ALL_BRANCHES, Category, Price, Product, Sku, Supplier, SupplierSku
from .pricing import current_prices
from .serializers import (
    CategorySerializer,
    PriceInputSerializer,
    ProductSerializer,
    SkuSerializer,
    SupplierSerializer,
    SupplierTermsInputSerializer,
)

READERS = (HQ_ADMIN, BRANCH_MANAGER)


class HqWrites:
    """Reads for HQ and managers, writes for HQ only."""

    def get_permissions(self):
        if self.request.method == "GET":
            return [HasRole(*READERS)()]
        return [HasRole(HQ_ADMIN)()]


def paginate(view, request, items, serialize):
    paginator = Pagination()
    page = paginator.paginate_queryset(items, request, view=view)
    return Response({"results": serialize(page), "count": paginator.page.paginator.count})


def products_data(products) -> list[dict]:
    """Products with their SKUs and each SKU's company-wide (ALL) price today."""
    data = ProductSerializer(products, many=True).data
    prices = current_prices([s["sku"] for p in data for s in p["skus"]], ALL_BRANCHES, timezone.localdate())
    for product in data:
        for sku in product["skus"]:
            price = prices.get(sku["sku"])
            sku["price"] = f"{price.amount:.2f}" if price else None
    return data


def price_data(price: Price) -> dict:
    return {
        "sku": price.sku_id,
        "branch_scope": price.branch_scope,
        "valid_from": price.valid_from,
        "amount": f"{price.amount:.2f}",
    }


class CategoryListView(HqWrites, APIView):
    """GET /categories · POST /categories {name, parent_id}"""

    def get(self, request):
        return paginate(self, request, Category.objects.all(), lambda page: CategorySerializer(page, many=True).data)

    def post(self, request):
        serializer = CategorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ProductListView(HqWrites, APIView):
    """GET /products?q=&category_id=&status= · POST /products (publishes E2 per SKU)"""

    def get(self, request):
        qs = Product.objects.select_related("category").prefetch_related("skus")
        q = request.query_params.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(name__icontains=q) | Q(brand__icontains=q) | Q(skus__sku__icontains=q) | Q(skus__barcode=q)
            ).distinct()
        if category_id := request.query_params.get("category_id"):
            qs = qs.filter(category_id=category_id)
        if status_filter := request.query_params.get("status"):
            qs = qs.filter(status=status_filter)
        return paginate(self, request, qs, products_data)

    def post(self, request):
        serializer = ProductSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            product = serializer.save()
            for sku in product.skus.all():
                publish_sku(sku)
        return Response(products_data([product])[0], status=status.HTTP_201_CREATED)


class ProductDetailView(HqWrites, APIView):
    """GET /products/{id} · PATCH /products/{id} (publishes E2 for every SKU of the product)"""

    def get(self, request, product_id):
        product = get_object_or_404(Product.objects.select_related("category"), pk=product_id)
        return Response(products_data([product])[0])

    def patch(self, request, product_id):
        with transaction.atomic():
            product = get_object_or_404(Product.objects.select_for_update(), pk=product_id)
            serializer = ProductSerializer(product, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            product = serializer.save()
            for sku in product.skus.select_related("product__category"):
                publish_sku(sku)
        return Response(products_data([product])[0])


class SkuDetailView(APIView):
    """GET /skus/{sku}: the SKU and every price row."""

    permission_classes = [HasRole(*READERS)]

    def get(self, request, sku):
        row = get_object_or_404(Sku, pk=sku)
        return Response(
            {
                **SkuSerializer(row).data,
                "product_id": row.product_id,
                "prices": [price_data(p) for p in row.prices.all()],
            }
        )


class PriceView(APIView):
    """GET /prices/{sku}?branch_id= (S6: today's price by the §5.2 rule) · PUT /prices/{sku} (HQ, publishes E3)"""

    def get_permissions(self):
        if self.request.method == "GET":
            return [(IsInternalService | HasRole(HQ_ADMIN, BRANCH_MANAGER, CASHIER, branch_from="branch_id"))()]
        return [HasRole(HQ_ADMIN)()]

    def get(self, request, sku):
        branch_id = request.query_params.get("branch_id")
        if not branch_id:
            raise ApiError("BRANCH_REQUIRED", "branch_id is required")
        row = get_object_or_404(Sku, pk=sku)
        price = current_prices([sku], branch_id, timezone.localdate()).get(sku)
        if price is None:
            raise ApiError("PRICE_NOT_FOUND", f"No price for {sku} at {branch_id}", status=status.HTTP_404_NOT_FOUND)
        return Response(
            {
                "sku": row.sku,
                "name": row.name,
                "barcode": row.barcode,
                "amount": f"{price.amount:.2f}",
                "valid_from": price.valid_from,
            }
        )

    def put(self, request, sku):
        serializer = PriceInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        row = get_object_or_404(Sku, pk=sku)
        with transaction.atomic():
            price, _ = Price.objects.update_or_create(
                sku=row,
                branch_scope=data["branch_scope"],
                valid_from=data["valid_from"],
                defaults={"amount": data["amount"]},
            )
            publish_price(price)
        return Response(price_data(price))


class SupplierListView(APIView):
    """GET /suppliers · POST /suppliers (HQ)"""

    permission_classes = [HasRole(HQ_ADMIN)]

    def get(self, request):
        return paginate(self, request, Supplier.objects.all(), lambda page: SupplierSerializer(page, many=True).data)

    def post(self, request):
        serializer = SupplierSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class SupplierDetailView(APIView):
    """PATCH /suppliers/{id} (HQ). A lead time change republishes E4 for every SKU the supplier sells."""

    permission_classes = [HasRole(HQ_ADMIN)]

    def patch(self, request, supplier_id):
        with transaction.atomic():
            supplier = get_object_or_404(Supplier.objects.select_for_update(), pk=supplier_id)
            serializer = SupplierSerializer(supplier, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            for terms in supplier.terms.select_related("supplier", "sku"):
                publish_terms(terms)
        return Response(serializer.data)


class SupplierSkuView(APIView):
    """PUT /suppliers/{id}/skus/{sku} {unit_cost, min_order_qty, is_preferred} (HQ, publishes E4).

    Making one supplier preferred demotes the SKU's other preferred supplier, and publishes that too.
    """

    permission_classes = [HasRole(HQ_ADMIN)]

    def put(self, request, supplier_id, sku):
        serializer = SupplierTermsInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        supplier = get_object_or_404(Supplier, pk=supplier_id)
        row = get_object_or_404(Sku, pk=sku)
        with transaction.atomic():
            if data["is_preferred"]:
                for other in (
                    SupplierSku.objects.select_for_update()
                    .filter(sku=row, is_preferred=True)
                    .exclude(supplier=supplier)
                ):
                    other.is_preferred = False
                    other.save(update_fields=["is_preferred"])
                    publish_terms(other)
            terms, _ = SupplierSku.objects.update_or_create(supplier=supplier, sku=row, defaults=data)
            publish_terms(terms)
        return Response(
            {
                "supplier_id": terms.supplier_id,
                "sku": terms.sku_id,
                "unit_cost": f"{terms.unit_cost:.2f}",
                "min_order_qty": terms.min_order_qty,
                "is_preferred": terms.is_preferred,
            }
        )
