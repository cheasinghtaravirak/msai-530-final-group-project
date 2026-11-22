from rest_framework.response import Response
from rest_framework.views import APIView

from retail_common.auth import BRANCH_MANAGER, HQ_ADMIN, HasRole

from .models import BranchRef


class BranchRefListView(APIView):
    """GET /refs/branches: the branches Inventory knows about (debug view of the event-fed copy)."""

    permission_classes = [HasRole(HQ_ADMIN, BRANCH_MANAGER)]

    def get(self, request):
        rows = list(BranchRef.objects.values("branch_id", "name", "status", "updated_at"))
        return Response({"results": rows, "count": len(rows)})
