"""The committed synthetic sample must be exactly reproducible from its generator."""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_sample_file_matches_generator_output(tmp_path):
    out = tmp_path / "sample.csv"
    subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "generate_sample_data.py"),
         "--rows", "5000", "--seed", "42", "--out", str(out)],
        check=True, capture_output=True,
    )  # fmt: skip
    committed = (REPO_ROOT / "data" / "sample" / "synthetic_transactions.csv").read_bytes()
    assert out.read_bytes() == committed.replace(b"\r\n", b"\n")
