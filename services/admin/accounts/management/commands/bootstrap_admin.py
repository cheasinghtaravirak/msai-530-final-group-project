"""Create the shop and the first HQ admin if they don't exist. Runs on every start; safe to repeat."""

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import AppUser, RoleGrant, Shop


class Command(BaseCommand):
    help = "Create the demo shop and HQ admin user if missing"

    @transaction.atomic
    def handle(self, *args, **options):
        if not Shop.objects.exists():
            Shop.objects.create(name="Demo Retail Co.", base_currency="USD")
            self.stdout.write("Created shop")

        email = settings.BOOTSTRAP_ADMIN_EMAIL
        user, created = AppUser.objects.get_or_create(email=email, defaults={"full_name": "HQ Admin"})
        if created:
            user.set_password(settings.BOOTSTRAP_ADMIN_PASSWORD)
            user.save()
            RoleGrant.objects.create(user=user, role_code=RoleGrant.Role.HQ_ADMIN)
            self.stdout.write(f"Created HQ admin {email}")
