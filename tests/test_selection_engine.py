from pathlib import Path
import sys
from unittest import TestCase, main

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from selection_engine import select_publishable_stories


def story(region, score, n):
    return {
        "region": region,
        "editor_score": score,
        "editor_rank": 100 - score,
        "canonical": f"example.com/{region.lower()}/{n}",
        "headline": f"Story {region} {n}",
    }


class SelectionTests(TestCase):
    def test_only_80_plus_is_publishable(self):
        selected = select_publishable_stories(
            [story("Bangladesh", 79, 1), story("Bangladesh", 80, 2)],
            [story("International", 81, 3), story("International", 50, 4)],
        )
        self.assertEqual([s["editor_score"] for s in selected], [81, 80])

    def test_no_fixed_three_plus_two_quota(self):
        selected = select_publishable_stories(
            [story("Bangladesh", s, i) for i, s in enumerate([99, 95, 90, 85])],
            [story("International", s, i) for i, s in enumerate([83])],
        )
        self.assertEqual(len(selected), 5)
        self.assertEqual(selected[0]["editor_score"], 99)
        self.assertEqual(selected[-1]["editor_score"], 83)

    def test_20_qualified_stories_all_selected(self):
        bd = [story("Bangladesh", 100 - i, i) for i in range(10)]
        intl = [story("International", 90 - i, i) for i in range(10)]
        selected = select_publishable_stories(bd, intl)
        self.assertEqual(len(selected), 20)
        self.assertTrue(all(s["editor_score"] >= 80 for s in selected))

    def test_more_than_20_is_capped_for_safety(self):
        bd = [story("Bangladesh", 100, i) for i in range(20)]
        intl = [story("International", 99, i) for i in range(20)]
        selected = select_publishable_stories(bd, intl)
        self.assertEqual(len(selected), 20)

    def test_both_regions_are_guaranteed_when_both_have_qualifiers(self):
        bd = [story("Bangladesh", 99, 1), story("Bangladesh", 95, 2)]
        intl = [story("International", 80, 1)]
        selected = select_publishable_stories(bd, intl)
        self.assertEqual({s["region"] for s in selected}, {"Bangladesh", "International"})
        self.assertEqual(selected[0]["editor_score"], 99)
        self.assertEqual(selected[-1]["editor_score"], 80)

    def test_missing_region_does_not_create_filler(self):
        selected = select_publishable_stories(
            [story("Bangladesh", 98, 1), story("Bangladesh", 81, 2)], []
        )
        self.assertEqual(len(selected), 2)
        self.assertTrue(all(s["region"] == "Bangladesh" for s in selected))

    def test_zero_qualifying_means_zero_posts(self):
        selected = select_publishable_stories(
            [story("Bangladesh", 79, 1)], [story("International", 79, 2)]
        )
        self.assertEqual(selected, [])

    def test_global_score_order_after_diversity_floor(self):
        selected = select_publishable_stories(
            [story("Bangladesh", 82, 1)],
            [story("International", 97, 1), story("International", 91, 2)],
        )
        self.assertEqual([s["editor_score"] for s in selected], [97, 91, 82])

    def test_duplicate_canonical_is_removed(self):
        bd = [story("Bangladesh", 95, 1)]
        intl = [story("International", 94, 1)]
        intl[0]["canonical"] = bd[0]["canonical"]
        selected = select_publishable_stories(bd, intl)
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["editor_score"], 95)


if __name__ == "__main__":
    main()
