"""The database a scan run matched against, on `compliance_scan_run`.

`req-compliance-core-scan-run-5`. Two nullable columns on the node and on its history table;
additive and backfill-free, so every existing run reads null (unobserved). The
`SCANNED_COMPLIANCE_TARGET` edge needs no migration: edge types are manifest-declared.
"""

from django.db import migrations, models

_FIELDS = {
    "data_version": lambda: models.CharField(
        blank=True,
        default=None,
        help_text="The version or build identifier of the vulnerability database the scanner matched against, "
        "as the scanner reports it. Null = unobserved.",
        max_length=128,
        null=True,
    ),
    "data_built_at": lambda: models.DateTimeField(
        blank=True,
        default=None,
        help_text="When that database says it was built, so a run against a stale database is visible.",
        null=True,
    ),
}


class Migration(migrations.Migration):

    dependencies = [
        ("compliance_core", "0006_vulnerability_epss_kev_detail"),
    ]

    operations = [
        migrations.AddField(model_name=model, name=name, field=make())
        for model in ("compliancescanrun", "historicalcompliancescanrun")
        for name, make in _FIELDS.items()
    ]
