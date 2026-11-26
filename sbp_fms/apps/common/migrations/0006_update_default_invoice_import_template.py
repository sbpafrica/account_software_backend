from django.db import migrations
from apps.common.imports.defaults import get_default_schema_for_entity


def update_default_invoice_templates(apps, schema_editor):
    ImportTemplate = apps.get_model("common", "ImportTemplate")
    new_schema = get_default_schema_for_entity("INVOICE")
    # Refresh any auto-created default INVOICE templates so they use the INCOME_2025 headers
    ImportTemplate.objects.filter(
        entity_type="INVOICE",
        is_default=True,
        name="Default Commercial & Tax Invoices Template",
    ).update(columns_schema=new_schema)


class Migration(migrations.Migration):

    dependencies = [
        ("common", "0005_alter_importjob_entity_type_and_more"),
    ]

    operations = [
        migrations.RunPython(update_default_invoice_templates, migrations.RunPython.noop),
    ]
