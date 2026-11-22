from rest_framework import serializers

from .models import Branch


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False)


class BranchSerializer(serializers.ModelSerializer):
    branch_id = serializers.RegexField(r"^BR-\d{2,4}$", max_length=10)

    class Meta:
        model = Branch
        fields = ["branch_id", "name", "address", "region", "timezone", "status", "opened_on"]
        read_only_fields = ["status"]

    def get_fields(self):
        fields = super().get_fields()
        if self.instance is not None:  # the ID never changes after creation
            fields["branch_id"].read_only = True
        return fields


def branch_event_payload(branch: Branch) -> dict:
    """Payload of branch.upserted (E1, design doc §6.3)."""
    return {
        "branch_id": branch.branch_id,
        "name": branch.name,
        "region": branch.region,
        "timezone": branch.timezone,
        "status": branch.status,
    }
