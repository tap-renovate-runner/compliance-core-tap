"""The data migration that retires `COVERS_COMPLIANCE_FINDING` rows whose source is an exception
(`req-compliance-core-exception-edges-5`)."""

from __future__ import annotations

import importlib
from datetime import UTC, datetime

import pytest
import tap_plugin.compliance_core.models as compliance  # noqa: F401 - trigger model registration
from django.apps import apps

from tap_grid.models import Edge, Entity

MIGRATION = importlib.import_module("tap_plugin.compliance_core.migrations.0011_retire_exception_covers_rows")
CC = "compliance_core__compliance_"
COVERS = "COVERS_COMPLIANCE_FINDING__compliance_core"

pytestmark = pytest.mark.django_db(transaction=True, databases=["default", "search_readonly"])


def _node(kind: str, name: str) -> Entity:
    return Entity.objects.create(entity_type=f"{CC}{kind}", name=name)


def _edge(source: Entity, target: Entity, edge_type: str = COVERS, **properties: str) -> Edge:
    """Written straight to the tables: the service layer would refuse the old shape, which is the point."""
    return Edge.objects.create(
        entity=Entity.objects.create(entity_type="edge", name=f"{source.name} {edge_type}"),
        from_entity=source,
        to_entity=target,
        edge_type=edge_type,
        properties=properties,
    )


def _run() -> None:
    MIGRATION.retire_old_covers(apps, None)


class TestRetireOldCovers:
    @pytest.mark.spec("req-compliance-core-exception-edges-5")
    def test_an_edge_from_an_exception_is_retired_with_its_spine_row(self) -> None:
        old = _edge(_node("exception", "ex"), _node("finding", "f"))
        edge_entity = old.entity_id
        _run()
        assert not Edge.objects.filter(pk=old.pk).exists()
        assert not Entity.objects.filter(pk=edge_entity).exists()

    @pytest.mark.spec("req-compliance-core-exception-edges-5")
    def test_it_touches_no_other_row(self) -> None:
        exception, instance, finding = (
            _node("exception", "ex"),
            _node("exception_instance", "inst"),
            _node("finding", "f"),
        )
        keep_new = _edge(instance, finding)  # the new shape
        keep_other = _edge(
            exception, finding, "CITES_COMPLIANCE_EVIDENCE__compliance_core", support_kind="informational"
        )  # another type from an exception
        _edge(exception, finding)  # the one to retire
        before = {(e.pk) for e in Entity.objects.exclude(entity_type="edge")}
        _run()
        assert Edge.objects.filter(pk=keep_new.pk).exists() and Edge.objects.filter(pk=keep_other.pk).exists()
        assert {e.pk for e in Entity.objects.exclude(entity_type="edge")} == before  # no node was touched
        assert Edge.objects.filter(edge_type=COVERS).count() == 1

    @pytest.mark.spec("req-compliance-core-exception-edges-5")
    def test_a_tombstoned_old_edge_is_left_as_history(self) -> None:
        old = _edge(_node("exception", "ex"), _node("finding", "f"))
        Entity.objects.filter(pk=old.entity_id).update(deleted_at=datetime.now(UTC))
        _run()
        assert Edge._base_manager.filter(pk=old.pk).exists()  # the live manager hides a tombstone

    @pytest.mark.spec("req-compliance-core-exception-edges-5")
    def test_it_is_safe_to_run_twice_and_on_an_empty_grid(self) -> None:
        _run()
        _edge(_node("exception", "ex"), _node("finding", "f"))
        _run()
        _run()
        assert Edge.objects.filter(edge_type=COVERS).count() == 0

    @pytest.mark.spec("req-compliance-core-exception-edges-5")
    def test_it_is_registered_after_the_snapshot_migration_and_does_not_reverse(self) -> None:
        assert MIGRATION.Migration.dependencies[0] == ("compliance_core", "0010_search_snapshot")
        (operation,) = MIGRATION.Migration.operations
        assert operation.reversible  # a no-op reverse, so an unapply does not fail; it does not restore rows

    @pytest.mark.spec("req-compliance-core-exception-edges-5")
    def test_the_real_migration_path_with_historical_models(self) -> None:
        """Roll back to 0010, leave an old-shape edge and a new-shape one, and migrate forward through the executor."""
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor

        MigrationExecutor(connection).migrate([("compliance_core", "0010_search_snapshot")])
        try:
            exception, instance, finding = (
                _node("exception", "ex"),
                _node("exception_instance", "inst"),
                _node("finding", "f"),
            )
            old, new = _edge(exception, finding), _edge(instance, finding)
        finally:
            MigrationExecutor(connection).migrate([("compliance_core", "0011_retire_exception_covers_rows")])
        assert not Edge.objects.filter(pk=old.pk).exists()
        assert Edge.objects.filter(pk=new.pk).exists()
