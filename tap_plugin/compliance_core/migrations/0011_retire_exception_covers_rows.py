"""Retire the old shape of `COVERS_COMPLIANCE_FINDING`: an edge whose source is an exception.

The edge moved to start at an exception instance (`req-compliance-core-exception-edges-4`), so a
live edge from a `compliance_core__compliance_exception` to a finding is a row the type no longer
allows and nothing reads: coverage is computed from the instance's edges
(`req-compliance-core-exception-coverage`). This retires those rows (the edge and its spine row)
and touches no other row: not an edge of another type, not an edge from an instance, not a
tombstoned edge, and no node. A tombstone is left as the grid's history of it.

Kept apart from the schema migrations, as `0003` was, and not reversible: a retired row is not
recreated, because the exception it came from never named an instance to bind it to. Ids of the
new shape derive from the slug, so a producer's next collection re-emits what is still true.
Release gate (`req-compliance-core-exception-edges-5`): the consumers that read the old shape are
retargeted or shown to have no reader before this is released.

Direct ORM access is the sanctioned path in migrations.
"""

from typing import Any

from django.db import migrations

COVERS = "COVERS_COMPLIANCE_FINDING__compliance_core"
EXCEPTION = "compliance_core__compliance_exception"


def retire_old_covers(apps: Any, schema_editor: Any) -> None:
    Edge = apps.get_model("tap_grid", "Edge")
    Entity = apps.get_model("tap_grid", "Entity")
    edges = Edge.objects.filter(
        edge_type=COVERS,
        from_entity__entity_type=EXCEPTION,
        entity__deleted_at__isnull=True,
    )
    entity_ids = list(edges.values_list("entity_id", flat=True))
    edges.delete()
    Entity.objects.filter(pk__in=entity_ids).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("compliance_core", "0010_search_snapshot"),
        ("tap_grid", "0001_initial"),
    ]

    operations = [migrations.RunPython(retire_old_covers, migrations.RunPython.noop)]
