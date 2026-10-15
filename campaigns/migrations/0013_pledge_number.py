import secrets

import wagtail.fields
from django.db import migrations, models


def number_existing_pledges(apps, schema_editor):
    """Give every pledge sent before pledge numbers a number of its own."""
    Pledge = apps.get_model("campaigns", "Pledge")
    taken = set()
    for pledge in Pledge.objects.filter(number__isnull=True).only("pk"):
        number = str(100000 + secrets.randbelow(900000))
        while number in taken:
            number = str(100000 + secrets.randbelow(900000))
        taken.add(number)
        Pledge.objects.filter(pk=pledge.pk).update(number=number)


class Migration(migrations.Migration):
    dependencies = [
        ("campaigns", "0012_payment_steps"),
    ]

    operations = [
        # Added empty, filled, then made unique: a unique column can't be added to a table with
        # rows in it until each row has its own value.
        migrations.AddField(
            model_name="pledge",
            name="number",
            field=models.CharField(
                editable=False, max_length=6, null=True, verbose_name="pledge number"
            ),
        ),
        migrations.RunPython(number_existing_pledges, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="pledge",
            name="number",
            field=models.CharField(
                editable=False, max_length=6, unique=True, verbose_name="pledge number"
            ),
        ),
        migrations.AlterField(
            model_name="donatepage",
            name="thank_you_text",
            field=wagtail.fields.RichTextField(
                blank=True,
                help_text="Shown after someone sends the form when there's no way to pay on the "
                "site yet.",
            ),
        ),
    ]
