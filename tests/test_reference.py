import unittest

import pandas as pd

from patent_diffusion._reference import build_pools


class OpportunityPoolTests(unittest.TestCase):
    @staticmethod
    def edges(citer_modulus=510):
        rows = []
        for fold in range(5):
            for pair in range(51):
                for ai in (0, 1):
                    rows.append({"fold": fold, "focal": 1, "lag_band": 0,
                                 "calendar_band": 0,
                                 "citing_id": f"c{(fold * 102 + pair * 2 + ai) % citer_modulus}",
                                 "mask": 2})
        return pd.DataFrame(rows)

    def test_pool_requires_minimum_edges_and_distinct_families(self):
        *_, unsupported = build_pools(self.edges())
        self.assertFalse(unsupported.any())

    def test_pool_rejects_fewer_than_50_distinct_families(self):
        *_, unsupported = build_pools(self.edges(citer_modulus=49))
        self.assertTrue(unsupported.all())

    def test_donor_pool_excludes_target_fold(self):
        e = self.edges()
        e["mask"] = e.fold + 1
        starts, counts, donors, unsupported = build_pools(e)
        self.assertFalse(unsupported.any())
        for i in range(0, len(e), 102):
            pool = donors[starts[i]:starts[i]+counts[i]]
            self.assertNotIn(int(e.iloc[i].fold)+1, set(pool))

    def test_fallback_does_not_cross_focal_field(self):
        e = self.edges()
        e.loc[:9, "focal"] = 2
        *_, unsupported = build_pools(e)
        self.assertTrue(unsupported[:10].all())
        self.assertFalse(unsupported[10:].any())


if __name__ == "__main__":
    unittest.main()