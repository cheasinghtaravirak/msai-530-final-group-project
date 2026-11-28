from django.utils import timezone
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from retail_common.api import ApiError
from retail_common.auth import BRANCH_MANAGER, HQ_ADMIN, HasRole

from .models import DimBranch
from .rollups import daily_sales

MAX_DAYS = 366


class DimBranchListView(APIView):
    """GET /dims/branches: branches as seen by Analytics (debug view of the event-fed copy)."""

    permission_classes = [HasRole(HQ_ADMIN, BRANCH_MANAGER)]

    def get(self, request):
        rows = list(DimBranch.objects.values("branch_id", "name", "region", "status"))
        return Response({"results": rows, "count": len(rows)})


SalesQuery = type(
    "SalesQuery",
    (serializers.Serializer,),
    {
        "scope": serializers.ChoiceField(["branch", "company"], default="branch"),
        "branch_id": serializers.CharField(max_length=10, required=False),
        "grain": serializers.ChoiceField(["day", "month"]),
        "from": serializers.DateField(required=False),
        "to": serializers.DateField(required=False),
    },
)


class SalesReportView(APIView):
    permission_classes = [HasRole(HQ_ADMIN, BRANCH_MANAGER, branch_from="branch_id")]

    def get(self, request):
        query = SalesQuery(data=request.query_params)
        query.is_valid(raise_exception=True)
        params = query.validated_data
        if params["scope"] != "branch" or params["grain"] != "day":
            raise ApiError("VALIDATION_ERROR", "Only scope=branch with grain=day is available until Phase 4")
        if "branch_id" not in params:
            raise ApiError("VALIDATION_ERROR", "branch_id is required", details={"branch_id": ["Required."]})
        today = timezone.localdate()
        first, last = params.get("from", today), params.get("to", today)
        if not 0 <= (last - first).days < MAX_DAYS:
            raise ApiError("VALIDATION_ERROR", f"from must be on or before to, at most {MAX_DAYS} days apart")
        rows = daily_sales(params["branch_id"], first, last, today)
        return Response({"results": rows, "count": len(rows)})
