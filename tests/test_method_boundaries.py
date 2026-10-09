import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from patent_diffusion import _reference, _study
from patent_diffusion.demo import make_demo_frames
from patent_diffusion.pipeline import _models


class MethodBoundaryTests(unittest.TestCase):
    def test_previously_reached_field_is_not_expansion(self):
        edges = pd.DataFrame({
            "focus_docdb_family_id": ["f"] * 4,
            "citing_docdb_family_id": ["a", "b", "c", "d"],
            "edge_event_date": pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03", "2020-01-04"]),
            "citing_wipo35_mask": [2, 4, 2, 4],
            "citing_wipo35_missing": [False] * 4,
            "focal_wipo35_field_nr": [1] * 4})
        r = _study.milestones(edges).iloc[0]
        self.assertEqual(r.establishment_date, pd.Timestamp("2020-01-03"))
        self.assertTrue(pd.isna(r.expansion_date))

    def test_dataframe_and_simulation_scorers_agree(self):
        f, e = make_demo_frames(pairs=80)
        f = f.sort_values("docdb_family_id").reset_index(drop=True)
        order = pd.Series(np.arange(len(f)), index=f.docdb_family_id)
        e["pos"] = e.focus_docdb_family_id.map(order)
        e = e.sort_values(["pos", "edge_event_date", "citing_docdb_family_id"])
        offsets = np.zeros(len(f)+1, dtype=np.int64)
        offsets[1:] = np.cumsum(np.bincount(e.pos, minlength=len(f)))
        actual = _reference.outcomes(offsets,
            (e.edge_event_date-pd.Timestamp("1970-01-01")).dt.days.to_numpy(np.int32),
            e.citing_wipo35_mask.to_numpy(np.uint64), f.wipo35_field_nr.to_numpy(np.int16))
        dates = _study.milestones(e).set_index("focus_docdb_family_id")
        expected = dates.reindex(f.docdb_family_id)[["arrival_date", "establishment_date", "expansion_date"]].notna().to_numpy(np.uint8)
        np.testing.assert_array_equal(actual, expected)
        self.assertTrue((actual[:, 2] <= actual[:, 1]).all())
        self.assertTrue((actual[:, 1] <= actual[:, 0]).all())

    def test_cox_cluster_alignment_is_independent_of_dataframe_index(self):
        f, e = make_demo_frames(pairs=80)
        first = e.groupby("focus_docdb_family_id").edge_event_date.min()
        f["first"] = f.docdb_family_id.map(first)
        f["horizon_end"] = f.focus_grant_date + pd.DateOffset(years=5)
        a = _study.fit_cox(f, "first", "test")
        shuffled = f.sample(frac=1, random_state=12)
        shuffled.index = np.arange(len(f)) * 3 + 19
        b = _study.fit_cox(shuffled, "first", "test")
        self.assertAlmostEqual(a["estimate"], b["estimate"], places=10)
        self.assertAlmostEqual(a["se_cluster"], b["se_cluster"], places=10)

    def test_singular_piecewise_fit_is_explicitly_unavailable(self):
        with patch("patent_diffusion.pipeline._study.conditional_binary", return_value={"estimate": 1.2}),              patch("patent_diffusion.pipeline._study.fit_cox", return_value={"ph_diagnostic": {"trigger_piecewise": True}}),              patch("patent_diffusion.pipeline.fit_piecewise", side_effect=np.linalg.LinAlgError("Singular matrix")):
            result = _models(None, 5, "H4", "h4", "date")
        self.assertEqual(result["estimate"], 1.2)
        self.assertEqual(result["piecewise_cox"]["status"], "not_estimable")
