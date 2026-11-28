from rest_framework import serializers

from .models import AppUser, Branch, RoleGrant


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


class RoleGrantSerializer(serializers.ModelSerializer):
    branch_id = serializers.PrimaryKeyRelatedField(
        source="branch", queryset=Branch.objects.all(), required=False, allow_null=True, default=None
    )

    class Meta:
        model = RoleGrant
        fields = ["grant_id", "role_code", "branch_id", "granted_at"]

    def validate(self, attrs):
        needs_branch = attrs["role_code"] in (RoleGrant.Role.BRANCH_MANAGER, RoleGrant.Role.CASHIER)
        if needs_branch != (attrs["branch"] is not None):
            raise serializers.ValidationError({"branch_id": "Required for branch roles, empty for HQ_ADMIN"})
        if attrs["branch"] is not None and attrs["branch"].status == Branch.Status.CLOSED:
            raise serializers.ValidationError({"branch_id": "Branch is closed"})
        return attrs


class UserSerializer(serializers.ModelSerializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8, trim_whitespace=False)
    roles = serializers.SerializerMethodField()

    class Meta:
        model = AppUser
        fields = ["user_id", "email", "full_name", "status", "password", "roles", "created_at"]
        read_only_fields = ["created_at"]

    def get_fields(self):
        fields = super().get_fields()
        if self.instance is not None:
            fields["email"].read_only = True
            fields["password"].required = False
        return fields

    def validate_email(self, value: str) -> str:
        value = value.lower()
        if AppUser.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists")
        return value

    def get_roles(self, user) -> list[dict]:
        return RoleGrantSerializer(user.active_grants().order_by("granted_at"), many=True).data

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = AppUser(**validated_data)
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        if password := validated_data.pop("password", None):
            instance.set_password(password)
        return super().update(instance, validated_data)
