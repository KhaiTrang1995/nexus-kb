from __future__ import annotations

import unittest

from tests import _paths  # noqa: F401

from nexus_shared.contracts import SourceType
from nexus_vector.client import build_search_filter


class BuildSearchFilterTest(unittest.TestCase):
    def test_no_filters_returns_none(self) -> None:
        self.assertIsNone(build_search_filter(tags=[], source_type=None))

    def test_workspace_ids_none_means_no_filter_admin_case(self) -> None:
        self.assertIsNone(build_search_filter(tags=[], source_type=None, workspace_ids=None))

    def test_workspace_ids_adds_match_any_condition(self) -> None:
        workspace_id = "11111111-1111-1111-1111-111111111111"
        result = build_search_filter(tags=[], source_type=None, workspace_ids=[workspace_id])
        self.assertIsNotNone(result)
        self.assertEqual(len(result.must), 1)
        self.assertEqual(result.must[0].key, "workspace_id")

    def test_empty_workspace_ids_list_still_produces_a_filter_fail_closed(self) -> None:
        # A user with zero workspace memberships must match nothing, not everything.
        result = build_search_filter(tags=[], source_type=None, workspace_ids=[])
        self.assertIsNotNone(result)
        self.assertEqual(result.must[0].match.any, [])

    def test_combines_tags_source_type_and_workspace_filters(self) -> None:
        result = build_search_filter(
            tags=["rag"], source_type=SourceType.OBSIDIAN, workspace_ids=["ws-1"]
        )
        keys = {condition.key for condition in result.must}
        self.assertEqual(keys, {"tags", "source_type", "workspace_id"})


if __name__ == "__main__":
    unittest.main()
