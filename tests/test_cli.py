import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class CLITests(unittest.TestCase):
    def test_help_and_version(self):
        for option in ("--help", "--version"):
            r = subprocess.run([sys.executable, "-m", "patent_diffusion", option], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_synthetic_end_to_end_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)/"demo"
            cmd = [sys.executable, "-m", "patent_diffusion", "demo", "--output", str(output)]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads(r.stdout)["dataset_kind"], "synthetic")
            manifest = json.loads((output/"results/run.json").read_text(encoding="utf-8"),
                                  parse_constant=lambda x: self.fail(f"non-standard JSON number {x}"))
            self.assertEqual(manifest["status"], "SMOKE_ONLY")
            self.assertEqual(set(manifest["windows"]), {"1Y", "3Y", "5Y"})
            for window in manifest["windows"].values():
                self.assertEqual(window["sampled_pairs"], 400)
                self.assertIsNone(window["comparison_with_paper"])
                self.assertGreater(window["opportunity_reference"]["supported_pairs"], 0)
                self.assertEqual(window["opportunity_reference"]["replicates"], 50)
            report = (output/"results/report.md").read_text(encoding="utf-8")
            self.assertIn("SYNTHETIC DATA", report)
            self.assertNotIn("Published full-cohort", report)
            self.assertEqual(len(manifest["families_sha256"]), 64)
            again = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(again.returncode, 2)
            self.assertIn("refusing to overwrite", again.stderr)
