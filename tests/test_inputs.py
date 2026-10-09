import tempfile
import unittest
from pathlib import Path

import pandas as pd

from patent_diffusion.demo import make_demo_frames
from patent_diffusion.pipeline import _validate, _sample, load_inputs, run, validate_inputs


class InputTests(unittest.TestCase):
    def setUp(self):
        self.f, self.e = make_demo_frames(pairs=60)

    def test_valid_synthetic_schema(self):
        _validate(self.f, self.e)

    def test_rejects_invalid_identifiers_masks_flags_and_dates(self):
        cases = [
            ("null pair", "f", "match_id", None),
            ("fractional field", "f", "wipo35_field_nr", 1.5),
            ("zero mask", "e", "citing_wipo35_mask", 0),
            ("fractional mask", "e", "citing_wipo35_mask", 1.5),
            ("negative mask", "e", "citing_wipo35_mask", -1),
            ("oversized mask", "e", "citing_wipo35_mask", 1 << 35),
            ("string missing flag", "e", "citing_wipo35_missing", "False"),
            ("future event", "e", "edge_event_date", pd.Timestamp("2030-01-01")),
            ("pregrant event", "e", "edge_event_date", pd.Timestamp("2000-01-01")),
        ]
        for label, which, column, value in cases:
            with self.subTest(label=label):
                f, e = self.f.copy(), self.e.copy()
                frame = f if which == "f" else e
                frame[column] = frame[column].astype(object)
                frame.loc[0, column] = value
                with self.assertRaises(ValueError):
                    _validate(f, e)

    def test_rejects_duplicate_and_within_family_edges(self):
        with self.assertRaisesRegex(ValueError, "unique"):
            _validate(self.f, pd.concat([self.e, self.e.iloc[:1]], ignore_index=True))
        e = self.e.copy()
        e.loc[0, "citing_docdb_family_id"] = e.loc[0, "focus_docdb_family_id"]
        with self.assertRaisesRegex(ValueError, "within-family"):
            _validate(self.f, e)

    def test_missing_columns_have_actionable_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            fp, ep = Path(tmp)/"f.parquet", Path(tmp)/"e.parquet"
            self.f.drop(columns="focus_grant_date").to_parquet(fp)
            self.e.to_parquet(ep)
            with self.assertRaisesRegex(ValueError, "families input missing columns"):
                load_inputs(fp, ep)

    def test_validation_is_read_only_and_sampling_is_order_invariant(self):
        with tempfile.TemporaryDirectory() as tmp:
            fp, ep = Path(tmp)/"f.parquet", Path(tmp)/"e.parquet"
            self.f.to_parquet(fp); self.e.to_parquet(ep)
            before = (fp.read_bytes(), ep.read_bytes())
            self.assertEqual(validate_inputs(fp, ep)["status"], "INPUTS_VALID")
            self.assertEqual(before, (fp.read_bytes(), ep.read_bytes()))
        a = _sample(self.f, 5, 12, 42)
        b = _sample(self.f.sample(frac=1, random_state=7), 5, 12, 42)
        self.assertEqual(set(a.docdb_family_id), set(b.docdb_family_id))
        self.assertEqual(len(a), 24)

    def test_no_overwrite_even_before_input_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileExistsError):
                run(Path("absent"), Path("absent"), Path(tmp))

    def test_rejects_underpowered_non_smoke_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "non-smoke"):
                run(Path("absent"), Path("absent"), Path(tmp)/"new", replicates=50)
