from retail_common.consumer import handles

from .models import BranchRef


@handles("branch.upserted")
def on_branch_upserted(event: dict) -> None:
    p = event["payload"]
    BranchRef.objects.update_or_create(branch_id=p["branch_id"], defaults={"name": p["name"], "status": p["status"]})
