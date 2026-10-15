"""Inspect built distributions before release; never uploads files."""
import json
import argparse
import re
import tarfile
import zipfile
from pathlib import Path


def check(directory=None):
    root = Path(__file__).resolve().parents[1]
    directory = Path(directory) if directory else root / "dist"
    archives = sorted(directory.glob("*.whl")) + sorted(directory.glob("*.tar.gz"))
    if not any(p.suffix == ".whl" for p in archives) or not any(p.name.endswith(".tar.gz") for p in archives):
        raise SystemExit("Build both a wheel and a source distribution first: python -m build")
    report = []
    for path in archives:
        if path.suffix == ".whl":
            with zipfile.ZipFile(path) as z:
                names = z.namelist()
                contents = {n:z.read(n) for n in names if not n.endswith('/')}
                metadata = z.read(next(n for n in names if n.endswith(".dist-info/METADATA"))).decode("utf-8")
                if "License-Expression: Apache-2.0" not in metadata:
                    raise SystemExit(f"Missing SPDX license metadata: {path.name}")
        else:
            with tarfile.open(path) as t:
                names = t.getnames()
                contents = {n.name:t.extractfile(n).read() for n in t.getmembers() if n.isfile()}
        forbidden = [name for name in names if
            any(part in {".venv", "outputs", "data", ".git", "__pycache__"} for part in Path(name).parts)
            or Path(name).suffix.lower() in {".parquet", ".csv", ".xlsx", ".docx", ".pdf", ".pem", ".key"}
            or Path(name).name.startswith(".env")]
        if forbidden:
            raise SystemExit(f"Unexpected private/generated files in {path.name}: {forbidden}")
        findings=[]
        for name,content in contents.items():
            if Path(name).suffix.lower() not in {'.py','.md','.json','.toml','.cff','.txt','.yml'}: continue
            value=content.decode('utf-8-sig')
            if re.search(r'[A-Za-z]:[\\/]Users[\\/][^\s/\\]+|[A-Za-z]:[\\/]AI [^\r\n]+workspace',value): findings.append(name+': personal path')
            if re.search(r'gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|AKIA[A-Z0-9]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',value): findings.append(name+': credential pattern')
        if findings: raise SystemExit('Content scan failed: '+str(findings))
        for required in ("LICENSE", "NOTICE", "patent_diffusion/reference_contract.json"):
            if not any(n.endswith("/" + required) or n == required for n in names):
                raise SystemExit(f"Missing {required}: {path.name}")
        report.append({"archive": path.name, "files": len(names), "status": "PASS", "content_scan":"personal paths and credential patterns; not a data-rights certification"})
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser=argparse.ArgumentParser(); parser.add_argument('--dist',type=Path)
    check(parser.parse_args().dist)
