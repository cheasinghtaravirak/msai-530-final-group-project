from rest_framework import serializers

from retail_common.api import ApiError
from retail_common.models import SKU_MAX_LENGTH

from .models import Category, Product, Sku, Supplier

SKU_CODE = rf"^[A-Z0-9][A-Z0-9-]{{0,{SKU_MAX_LENGTH - 1}}}$"
BRANCH_SCOPE = r"^(ALL|BR-\d{2,4})$"
MONEY = {"max_digits": 12, "decimal_places": 2, "min_value": 0}


class CategorySerializer(serializers.ModelSerializer):
    parent_id = serializers.PrimaryKeyRelatedField(
        source="parent", queryset=Category.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = Category
        fields = ["category_id", "parent_id", "name"]


class SkuInputSerializer(serializers.Serializer):
    sku = serializers.RegexField(SKU_CODE)
    name = serializers.CharField(max_length=200)
    barcode = serializers.CharField(max_length=50, allow_null=True)
    unit = serializers.ChoiceField(Sku.Unit.choices)
    pack_size = serializers.IntegerField(min_value=1)


class SkuSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sku
        fields = ["sku", "name", "barcode", "unit", "pack_size"]


class ProductSerializer(serializers.ModelSerializer):
    category_id = serializers.PrimaryKeyRelatedField(source="category", queryset=Category.objects.all())
    category = serializers.CharField(source="category.name", read_only=True)
    skus = SkuInputSerializer(many=True, required=False)

    class Meta:
        model = Product
        fields = ["product_id", "category_id", "category", "name", "brand", "status", "skus"]

    def validate_skus(self, skus):
        # A partial PATCH makes nested fields optional too, so validate the SKUs again on their own.
        whole = SkuInputSerializer(data=self.initial_data["skus"], many=True)
        whole.is_valid(raise_exception=True)
        skus = whole.validated_data
        codes = [s["sku"] for s in skus]
        barcodes = [s["barcode"] for s in skus if s["barcode"]]
        if len(set(codes)) != len(codes) or len(set(barcodes)) != len(barcodes):
            raise serializers.ValidationError("SKU codes and barcodes must be unique within the product")
        return skus

    def validate(self, attrs):
        if self.instance is None and not attrs.get("skus"):
            raise serializers.ValidationError({"skus": "A new product needs at least one SKU"})
        return attrs

    def create(self, validated_data):
        skus = validated_data.pop("skus")
        product = super().create(validated_data)
        _upsert_skus(product, skus)
        return product

    def update(self, instance, validated_data):
        skus = validated_data.pop("skus", [])
        product = super().update(instance, validated_data)
        _upsert_skus(product, skus)
        return product


def _upsert_skus(product: Product, skus: list[dict]) -> None:
    for fields in skus:
        code = fields.pop("sku")
        if Sku.objects.filter(pk=code).exclude(product=product).exists():
            raise ApiError("SKU_TAKEN", f"{code} belongs to another product", status=409)
        if fields["barcode"] and Sku.objects.filter(barcode=fields["barcode"]).exclude(pk=code).exists():
            raise ApiError("BARCODE_TAKEN", f"Barcode {fields['barcode']} is used by another SKU", status=409)
        Sku.objects.update_or_create(sku=code, defaults={**fields, "product": product})


class PriceInputSerializer(serializers.Serializer):
    branch_scope = serializers.RegexField(BRANCH_SCOPE)
    amount = serializers.DecimalField(**MONEY)
    valid_from = serializers.DateField()


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ["supplier_id", "name", "contact_email", "lead_time_days"]


class SupplierTermsInputSerializer(serializers.Serializer):
    unit_cost = serializers.DecimalField(**MONEY)
    min_order_qty = serializers.IntegerField(min_value=1, default=1)
    is_preferred = serializers.BooleanField(default=False)
