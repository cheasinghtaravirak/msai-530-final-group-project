import pytest
from products.models import Category, Product, Sku
from rest_framework.test import APIClient

from retail_common.auth import HQ_ADMIN, TokenUser

pytestmark = pytest.mark.django_db


@pytest.fixture
def hq():
    client = APIClient()
    client.force_authenticate(TokenUser(id="hq", roles=[{"role": HQ_ADMIN, "branch_id": None}]))
    return client


@pytest.fixture
def product():
    category = Category.objects.create(name="Test category")
    product = Product.objects.create(category=category, name="Test cola")
    Sku.objects.create(sku="TEST-COLA", product=product, name="Test cola 330 ml", barcode="0000000000017")
    return product


@pytest.mark.parametrize(
    "skus",
    [
        [{"sku": "TEST-COLA-2", "name": "Test cola 1 l"}],
        [{"sku": "TEST-COLA-2", "barcode": None}],
    ],
)
def test_patch_with_incomplete_skus_is_rejected(hq, product, skus):
    response = hq.patch(f"/products/{product.product_id}", {"skus": skus}, format="json")

    assert response.status_code == 400
    assert not Sku.objects.filter(pk="TEST-COLA-2").exists()


def test_patch_without_skus_keeps_them(hq, product):
    response = hq.patch(f"/products/{product.product_id}", {"name": "Test cola classic"}, format="json")

    assert response.status_code == 200
    assert response.json()["name"] == "Test cola classic"
    assert [s["sku"] for s in response.json()["skus"]] == ["TEST-COLA"]


def test_patch_with_complete_skus_adds_them(hq, product):
    skus = [{"sku": "TEST-COLA-2", "name": "Test cola 1 l", "barcode": None, "unit": "EA", "pack_size": 6}]

    response = hq.patch(f"/products/{product.product_id}", {"skus": skus}, format="json")

    assert response.status_code == 200
    assert Sku.objects.get(pk="TEST-COLA-2").pack_size == 6
