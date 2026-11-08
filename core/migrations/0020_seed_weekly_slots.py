from datetime import time

from django.db import migrations


def seed(apps, schema_editor):
    Slot = apps.get_model("core", "WeeklySlot")
    if not Slot.objects.exists():
        for start, end in [
            (time(11, 30), time(12, 45)),
            (time(13), time(14, 15)),
            (time(14, 30), time(15, 45)),
            (time(16), time(17, 15)),
        ]:
            Slot.objects.create(
                label=f"Standard play {start:%H:%M}",
                weekdays=[0, 1, 2, 3, 4, 6],
                starts_at=start,
                ends_at=end,
                public=True,
                play_mode="accompanied",
            )


class Migration(migrations.Migration):
    dependencies = [("core", "0019_session_recurring_managed_session_source_day_and_more")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
