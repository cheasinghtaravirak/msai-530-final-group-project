from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from retail_common.api import ApiError
from retail_common.auth import HQ_ADMIN, HasRole

from .models import JobRun
from .registry import JOBS


class JobRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobRun
        fields = ["run_id", "job", "trigger", "status", "requested_by", "message", "created_at", "started_at", "finished_at"]


class RunJobView(APIView):
    """POST /jobs/{job}/run (HQ only): queue a job; the scheduler starts it within ~3 seconds."""

    permission_classes = [HasRole(HQ_ADMIN)]

    def post(self, request, job):
        if job not in JOBS:
            raise ApiError("UNKNOWN_JOB", f"Unknown job {job!r}", status=status.HTTP_404_NOT_FOUND, details={"jobs": sorted(JOBS)})
        run = JobRun.objects.create(job=job, trigger=JobRun.Trigger.MANUAL, requested_by=request.user.id)
        return Response(JobRunSerializer(run).data, status=status.HTTP_202_ACCEPTED)


class JobRunListView(APIView):
    """GET /jobs/runs?job=&limit= (HQ only)"""

    permission_classes = [HasRole(HQ_ADMIN)]

    def get(self, request):
        qs = JobRun.objects.all()
        if job := request.query_params.get("job"):
            qs = qs.filter(job=job)
        limit = min(int(request.query_params.get("limit", 50)), 200)
        return Response({"results": JobRunSerializer(qs[:limit], many=True).data, "jobs": sorted(JOBS)})


class JobRunDetailView(APIView):
    """GET /jobs/runs/{run_id} (HQ only): poll a run's status."""

    permission_classes = [HasRole(HQ_ADMIN)]

    def get(self, request, run_id):
        run = JobRun.objects.filter(pk=run_id).first()
        if run is None:
            raise ApiError("NOT_FOUND", "No such run", status=status.HTTP_404_NOT_FOUND)
        return Response(JobRunSerializer(run).data)
