"""Inspect built distributions before release; never uploads files."""
import json
import tarfile
import zipfile
from pathlib import Path


def check():
    root = Path(__file__).resolve().parents[1]
    archives = sorted((root / "dist").glob("*.whl")) + sorted((root / "dist").glob("*.tar.gz"))
    if not any(p.suffix == ".whl" for p in archives) or not any(p.name.endswith(".tar.gz") for p in archives):
        raise SystemExit("Build both a wheel and a source distribution first: python -m build")
    report = []
    for path in archives:
        if path.suffix == ".whl":
            with zipfile.ZipFile(path) as z:
                names = z.namelist()
                metadata = z.read(next(n for n in names if n.endswith(".dist-info/METADATA"))).decode("utf-8")
                if "License-Expression: Apache-2.0" not in metadata:
                    raise SystemExit(f"Missing SPDX license metadata: {path.name}")
        else:
            with tarfile.open(path) as t:
                names = t.getnames()
        forbidden = [name for name in names if
            any(part in {".venv", "outputs", "data", ".git", "__pycache__"} for part in Path(name).parts)
            or Path(name).suffix.lower() in {".parquet", ".csv", ".xlsx", ".docx", ".pdf", ".pem", ".key"}
            or Path(name).name.startswith(".env")]
        if forbidden:
            raise SystemExit(f"Unexpected private/generated files in {path.name}: {forbidden}")
        for required in ("LICENSE", "NOTICE", "patent_diffusion/reference_contract.json"):
            if not any(n.endswith("/" + required) or n == required for n in names):
                raise SystemExit(f"Missing {required}: {path.name}")
        report.append({"archive": path.name, "files": len(names), "status": "PASS"})
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    check()
