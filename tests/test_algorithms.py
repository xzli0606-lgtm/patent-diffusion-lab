import unittest

import pandas as pd

from patent_diffusion._study import milestones


class MilestoneTests(unittest.TestCase):
    @staticmethod
    def edges(rows):
        frame = pd.DataFrame(rows, columns=["focus_docdb_family_id", "citing_docdb_family_id",
                                            "edge_event_date", "citing_wipo35_mask",
                                            "citing_wipo35_missing"])
        frame["edge_event_date"] = pd.to_datetime(frame.edge_event_date)
        frame["focal_wipo35_field_nr"] = 1
        return frame

    def test_same_day_does_not_establish_and_later_new_field_expands(self):
        result = milestones(self.edges([
            ("f", "a", "2020-01-01", 1 << 1, False),
            ("f", "b", "2020-01-01", 1 << 1, False),
            ("f", "c", "2020-01-03", 1 << 1, False),
            ("f", "d", "2020-01-03", 1 << 2, False),
            ("f", "e", "2020-01-04", 1 << 3, False),
        ])).iloc[0]
        self.assertEqual(result.arrival_date, pd.Timestamp("2020-01-01"))
        self.assertEqual(result.establishment_date, pd.Timestamp("2020-01-03"))
        self.assertEqual(result.expansion_date, pd.Timestamp("2020-01-04"))

    def test_distinct_citing_families_are_required(self):
        result = milestones(self.edges([
            ("f", "a", "2020-01-01", 1 << 1, False),
        ])).iloc[0]
        self.assertTrue(pd.isna(result.establishment_date))
        self.assertTrue(pd.isna(result.expansion_date))


if __name__ == "__main__":
    unittest.main()
