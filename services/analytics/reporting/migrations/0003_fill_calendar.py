from datetime import date, timedelta

from django.db import migrations

FIRST_DAY = date(2025, 1, 1)
LAST_DAY = date(2027, 12, 31)


def fill_calendar(apps, schema_editor):
    Calendar = apps.get_model("reporting", "Calendar")
    days = (FIRST_DAY + timedelta(n) for n in range((LAST_DAY - FIRST_DAY).days + 1))
    Calendar.objects.bulk_create(
        [Calendar(calendar_date=d, iso_week=d.isocalendar().week, weekday=d.isoweekday()) for d in days],
        ignore_conflicts=True,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("reporting", "0002_star_schema"),
    ]

    operations = [
        migrations.RunPython(fill_calendar, migrations.RunPython.noop),
    ]
