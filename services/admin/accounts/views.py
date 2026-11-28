from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from retail_common.api import ApiError
from retail_common.auth import BRANCH_MANAGER, CASHIER, HQ_ADMIN, HasRole
from retail_common.events import publish_event

from .models import AppUser, Branch, RoleGrant, Shop
from .serializers import BranchSerializer, LoginSerializer, RoleGrantSerializer, UserSerializer, branch_event_payload
from .tokens import issue_token


class LoginView(APIView):
    """POST /auth/login {email, password} -> {access_token, token_type, expires_in, user}"""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    def post(self, request):
        data = LoginSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = AppUser.objects.filter(email__iexact=data.validated_data["email"]).first()
        if (
            user is None
            or user.status != AppUser.Status.ACTIVE
            or not user.check_password(data.validated_data["password"])
        ):
            raise ApiError("INVALID_CREDENTIALS", "Wrong email or password", status=status.HTTP_401_UNAUTHORIZED)

        token, expires_in, claims = issue_token(user)
        return Response(
            {
                "access_token": token,
                "token_type": "Bearer",
                "expires_in": expires_in,
                "user": {
                    "user_id": claims["sub"],
                    "full_name": claims["name"],
                    "email": claims["email"],
                    "roles": claims["roles"],
                },
            }
        )


class MeView(APIView):
    """GET /auth/me -> the caller, as seen in their token."""

    def get(self, request):
        u = request.user
        return Response({"user_id": u.id, "full_name": u.name, "email": u.email, "roles": u.roles})


STAFF = (HQ_ADMIN, BRANCH_MANAGER, CASHIER)


class BranchListView(APIView):
    """GET /branches (staff: HQ sees all, others their own) · POST /branches (HQ only)"""

    def get_permissions(self):
        if self.request.method == "POST":
            return [HasRole(HQ_ADMIN)()]
        return [HasRole(*STAFF)()]

    def get(self, request):
        qs = Branch.objects.all()
        allowed = request.user.branch_ids(*STAFF)
        if allowed is not None:
            qs = qs.filter(branch_id__in=allowed)
        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return Response({"results": BranchSerializer(qs, many=True).data, "count": qs.count()})

    def post(self, request):
        serializer = BranchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if Branch.objects.filter(branch_id=serializer.validated_data["branch_id"]).exists():
            raise ApiError("BRANCH_EXISTS", "A branch with this ID already exists", status=status.HTTP_409_CONFLICT)
        shop = Shop.objects.first()
        if shop is None:
            raise ApiError("NO_SHOP", "Run the bootstrap first", status=status.HTTP_409_CONFLICT)

        with transaction.atomic():
            branch = serializer.save(shop=shop)
            publish_event("branch.upserted", branch_event_payload(branch), key=branch.branch_id)
        return Response(BranchSerializer(branch).data, status=status.HTTP_201_CREATED)


class BranchDetailView(APIView):
    """GET /branches/{id} · PATCH /branches/{id} (HQ only)"""

    def get_permissions(self):
        if self.request.method == "PATCH":
            return [HasRole(HQ_ADMIN)()]
        return [HasRole(*STAFF, branch_from="branch_id")()]

    def get(self, request, branch_id):
        return Response(BranchSerializer(get_object_or_404(Branch, pk=branch_id)).data)

    def patch(self, request, branch_id):
        with transaction.atomic():
            branch = get_object_or_404(Branch.objects.select_for_update(), pk=branch_id)
            serializer = BranchSerializer(branch, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            branch = serializer.save()
            publish_event("branch.upserted", branch_event_payload(branch), key=branch.branch_id)
        return Response(BranchSerializer(branch).data)


class BranchCloseView(APIView):
    permission_classes = [HasRole(HQ_ADMIN)]

    def post(self, request, branch_id):
        with transaction.atomic():
            branch = get_object_or_404(Branch.objects.select_for_update(), pk=branch_id)
            branch.status = Branch.Status.CLOSED
            branch.save(update_fields=["status"])
            branch.grants.filter(revoked_at__isnull=True).update(revoked_at=timezone.now())
            publish_event("branch.upserted", branch_event_payload(branch), key=branch.branch_id)
        return Response(BranchSerializer(branch).data)


class UserListView(APIView):
    permission_classes = [HasRole(HQ_ADMIN)]

    def get(self, request):
        qs = AppUser.objects.all()
        if q := request.query_params.get("q", "").strip():
            qs = qs.filter(Q(email__icontains=q) | Q(full_name__icontains=q))
        return Response({"results": UserSerializer(qs, many=True).data, "count": qs.count()})

    def post(self, request):
        serializer = UserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class UserDetailView(APIView):
    permission_classes = [HasRole(HQ_ADMIN)]

    def get(self, request, user_id):
        return Response(UserSerializer(get_object_or_404(AppUser, pk=user_id)).data)

    def patch(self, request, user_id):
        serializer = UserSerializer(get_object_or_404(AppUser, pk=user_id), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class UserRolesView(APIView):
    permission_classes = [HasRole(HQ_ADMIN)]

    def post(self, request, user_id):
        user = get_object_or_404(AppUser, pk=user_id)
        serializer = RoleGrantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        existing = user.active_grants().filter(role_code=data["role_code"], branch=data["branch"]).first()
        if existing:
            return Response(RoleGrantSerializer(existing).data)
        grant = serializer.save(user=user)
        return Response(RoleGrantSerializer(grant).data, status=status.HTTP_201_CREATED)


class UserRoleDetailView(APIView):
    permission_classes = [HasRole(HQ_ADMIN)]

    def delete(self, request, user_id, grant_id):
        grant = get_object_or_404(RoleGrant, pk=grant_id, user_id=user_id)
        if grant.revoked_at is None:
            grant.revoked_at = timezone.now()
            grant.save(update_fields=["revoked_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)
