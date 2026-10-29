"""The finding's detection time (`req-compliance-core-finding-detection`).

`first_detected_at` is when the producer first detected a finding, as its own record gives it.
It is null until a source says (never defaulted to the time this grid first saw the finding), it is
checked as a date-time, it is not part of the finding's identity, and a node under an existing key
changes only the fields it carries on a core with the keep-absent upsert (tap#1128), so a re-send that
omits it keeps the stored value and only an explicit null clears it; an older core replaces the row.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
import tap_plugin.compliance_core.models as compliance  # noqa: F401 - trigger model registration

from tap_grid.grift import grift_import
from tap_grid.models import Entity
from tap_grid.registry import get_model_class
from tap_grid.service_types import WriteOperation
from tap_grid.services import create_node

# A core release that carries the keep-absent upsert (tap#1128) leaves an omitted field alone; an older
# release replaces the whole row. The plugin's CI runs against both, so the test follows the core's capability.
KEEPS_ABSENT = "absent" in WriteOperation.__dataclass_fields__

FINDING_TYPE = "compliance_core__compliance_finding"
FINDING = {"source": "github_core", "source_key": "unified-systems-com/tap#code_scanning#7", "name": "CVE-2026-1"}


def _create(payload: dict[str, Any]) -> Any:
    result = create_node(FINDING_TYPE, payload)
    assert result.success, f"create_node failed: {result.errors}"
    return get_model_class(FINDING_TYPE).objects.get(entity=Entity.objects.get(pk=result.entity_id))


def _doc(fields: dict[str, Any]) -> dict[str, Any]:
    return {
        "metadata": {"grift_version": "0"},
        "_reserved": {},
        "batches": [
            {
                "batch_entity": {
                    "entity_id": str(uuid.uuid4()),
                    "entity_type": "batch",
                    "name": "finding detection time test batch",
                    "dimensions": {},
                },
                "batch_node": {
                    "name": "finding detection time test batch",
                    "description": "",
                    "description_json": None,
                    "source": "test",
                    "metadata": {},
                },
                "nodes": [
                    {
                        "entity": {
                            "ref": "f",
                            "entity_type": FINDING_TYPE,
                            "name": fields["name"],
                            "dimensions": {},
                        },
                        "node": dict(fields),
                    }
                ],
                "edges": [],
            }
        ],
    }


@pytest.mark.django_db
class TestFirstDetectedAt:
    def test_an_unwritten_value_is_unobserved(self) -> None:
        """req-compliance-core-finding-detection-1: null is "no source said", never a default."""
        assert _create(FINDING).first_detected_at is None

    def test_a_written_value_round_trips_as_a_datetime(self) -> None:
        """req-compliance-core-finding-detection-2."""
        finding = _create({**FINDING, "first_detected_at": "2026-09-25T12:45:55Z"})
        assert finding.first_detected_at.isoformat() == "2026-09-25T12:45:55+00:00"

    def test_an_explicit_null_is_accepted(self) -> None:
        assert _create({**FINDING, "first_detected_at": None}).first_detected_at is None

    @pytest.mark.parametrize("bad", ["yesterday", "25 Sep 2026", "2026-09-25", 7, True, {"at": "2026-09-25T12:45:55Z"}])
    def test_a_value_that_is_not_a_date_time_is_refused(self, bad: Any) -> None:
        """req-compliance-core-finding-detection-3.

        A bare ISO date ("2026-09-25") is refused on purpose. The platform's date-time field would read
        it as midnight (observed 2026-10-19), inventing a precision the producer never gave, and a
        deadline counted from this field would shift by up to a day. The schema's `pattern` requires
        the time part.
        """
        assert not create_node(FINDING_TYPE, {**FINDING, "first_detected_at": bad}).success

    def test_it_is_not_part_of_the_identity(self) -> None:
        """req-compliance-core-finding-detection-4: a corrected time is the same finding, not a new one."""
        model = get_model_class(FINDING_TYPE)
        ids = []
        for stamp in ("2026-09-25T12:45:55Z", "2026-09-20T08:00:00Z"):
            result = grift_import(_doc({**FINDING, "first_detected_at": stamp}))
            assert result.success, result.errors
            ids.append(result.imported_batches[0].resolved_refs["f"])
        assert ids[0] == ids[1]
        assert model.objects.live().count() == 1
        assert model.objects.live().get().first_detected_at.isoformat() == "2026-09-20T08:00:00+00:00"

    def test_a_replaced_value_stays_in_the_findings_history(self) -> None:
        """req-compliance-core-finding-detection-6: the field is mutable, but a change is never lost.

        A producer can move or clear the time, and compliance_core does not stop it (the resend duty
        is the producer's). What it does guarantee is that the earlier value is still on record in the
        finding's history after the live row has been replaced.
        """
        model = get_model_class(FINDING_TYPE)
        assert grift_import(_doc({**FINDING, "first_detected_at": "2026-09-20T08:00:00Z"})).success
        assert grift_import(_doc({**FINDING, "first_detected_at": "2026-09-25T12:45:55Z"})).success
        assert grift_import(_doc({**FINDING, "first_detected_at": None})).success
        row = model.objects.live().get()
        assert row.first_detected_at is None
        recorded = {h.first_detected_at.isoformat() for h in row.history.all() if h.first_detected_at is not None}
        assert recorded == {"2026-09-20T08:00:00+00:00", "2026-09-25T12:45:55+00:00"}

    def test_a_resend_without_it_keeps_the_value(self) -> None:
        """req-compliance-core-finding-detection-5: pins the platform behaviour the producer duty rests on.

        On a core that carries the keep-absent upsert (tap#1128) a GRIFT node under an existing key changes
        only the fields it carries, so a producer that re-sends this finding and leaves the field out keeps
        it. On an older core the row is replaced and the field goes back to null, which is why the producer
        should still send it. If a core with the capability ever goes back to replacing, this test fails.
        """
        model = get_model_class(FINDING_TYPE)
        assert grift_import(_doc({**FINDING, "first_detected_at": "2026-09-25T12:45:55Z"})).success
        assert grift_import(_doc(dict(FINDING))).success
        assert model.objects.live().count() == 1
        kept = model.objects.live().get().first_detected_at
        assert (kept.isoformat() if kept else None) == ("2026-09-25T12:45:55+00:00" if KEEPS_ABSENT else None)

    def test_an_explicit_null_clears_it(self) -> None:
        """req-compliance-core-finding-detection-5: only a null the producer sends clears the field."""
        model = get_model_class(FINDING_TYPE)
        assert grift_import(_doc({**FINDING, "first_detected_at": "2026-09-25T12:45:55Z"})).success
        assert grift_import(_doc({**FINDING, "first_detected_at": None})).success
        assert model.objects.live().get().first_detected_at is None
