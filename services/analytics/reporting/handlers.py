from retail_common.consumer import handles

from .models import DimBranch


@handles("branch.upserted")
def on_branch_upserted(event: dict) -> None:
    p = event["payload"]
    DimBranch.objects.update_or_create(
        branch_id=p["branch_id"],
        defaults={"name": p["name"], "region": p["region"], "status": p["status"]},
    )
