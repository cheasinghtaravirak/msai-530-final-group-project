from rest_framework.response import Response
from rest_framework.views import APIView

from retail_common.auth import BRANCH_MANAGER, HQ_ADMIN, HasRole

from .models import DimBranch


class DimBranchListView(APIView):
    """GET /dims/branches: branches as seen by Analytics (debug view of the event-fed copy)."""

    permission_classes = [HasRole(HQ_ADMIN, BRANCH_MANAGER)]

    def get(self, request):
        rows = list(DimBranch.objects.values("branch_id", "name", "region", "status"))
        return Response({"results": rows, "count": len(rows)})
