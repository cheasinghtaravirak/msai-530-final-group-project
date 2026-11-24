import pytest
from accounts.models import AppUser, Branch, RoleGrant, Shop
from rest_framework.test import APIClient

from retail_common.auth import HQ_ADMIN, TokenUser
from retail_common.models import Outbox

pytestmark = pytest.mark.django_db


@pytest.fixture
def hq():
    client = APIClient()
    client.force_authenticate(TokenUser(id="hq", roles=[{"role": HQ_ADMIN, "branch_id": None}]))
    return client


def test_closing_a_branch_revokes_its_grants_and_publishes_branch_upserted(hq):
    shop = Shop.objects.first() or Shop.objects.create(name="Test shop")
    branch = Branch.objects.create(branch_id="BR-9901", shop=shop, name="Test branch", region="KAMPOT")
    user = AppUser.objects.create(email="test.cashier@example.com", full_name="Test", password_hash="x")
    RoleGrant.objects.create(user=user, role_code="CASHIER", branch=branch)

    response = hq.post("/branches/BR-9901/close")

    assert response.status_code == 200
    assert response.json()["status"] == "CLOSED"
    assert not user.active_grants().exists()
    event = Outbox.objects.filter(event_type="branch.upserted", key="BR-9901").get()
    assert event.envelope["payload"]["status"] == "CLOSED"


def test_granting_the_same_role_twice_keeps_one_grant(hq):
    user = hq.post(
        "/users", {"email": "Test.Manager@example.com", "full_name": "Test", "password": "secret123"}, format="json"
    ).json()
    assert user["email"] == "test.manager@example.com"
    shop = Shop.objects.first() or Shop.objects.create(name="Test shop")
    Branch.objects.create(branch_id="BR-9902", shop=shop, name="Test branch", region="KAMPOT")

    grant = {"role_code": "BRANCH_MANAGER", "branch_id": "BR-9902"}
    first = hq.post(f"/users/{user['user_id']}/roles", grant, format="json")
    second = hq.post(f"/users/{user['user_id']}/roles", grant, format="json")

    assert (first.status_code, second.status_code) == (201, 200)
    assert first.json()["grant_id"] == second.json()["grant_id"]


@pytest.mark.parametrize("zone", ["Asia/Phnom Penh", "Asia/Bangkok"])
def test_a_branch_time_zone_other_than_the_business_zone_is_refused(hq, zone):
    shop = Shop.objects.first() or Shop.objects.create(name="Test shop")
    Branch.objects.create(branch_id="BR-9904", shop=shop, name="Test branch", region="KAMPOT")

    patched = hq.patch("/branches/BR-9904", {"timezone": zone}, format="json")
    created = hq.post(
        "/branches", {"branch_id": "BR-9905", "name": "Test", "region": "KAMPOT", "timezone": zone}, format="json"
    )

    assert (patched.status_code, created.status_code) == (400, 400)
    assert Branch.objects.get(pk="BR-9904").timezone == "Asia/Phnom_Penh"
    assert not Branch.objects.filter(pk="BR-9905").exists()
