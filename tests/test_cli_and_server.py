import json
import subprocess
import sys
from pathlib import Path

from upwork_kit import cli

ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "examples"


def test_cli_score_json(capsys):
    rc = cli.main(["score", str(EX / "job_good.json"), "--now", "2026-10-12T12:00:00Z"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["verdict"] == "bid"


def test_cli_rate(capsys):
    assert cli.main(["rate", "net_to_gross", "20", "--fee", "10"]) == 0
    assert json.loads(capsys.readouterr().out)["bill_hourly"] == 22.22


def test_cli_invalid_input_exit_2(capsys):
    assert cli.main(["rate", "fixed", "100", "--fee", "99"]) == 2
    assert "fee_percent" in capsys.readouterr().err


def test_cli_missing_file_exit_2(capsys):
    assert cli.main(["flags", str(EX / "nope.txt")]) == 2


def test_cli_lint_exit_code_reflects_errors(capsys):
    assert cli.main(["lint", str(EX / "proposal_draft.txt")]) == 1  # contains an unfilled [FILL: ...]
    capsys.readouterr()


def test_cli_flags(capsys):
    assert cli.main(["flags", str(EX / "job_bad.json")]) == 0
    assert json.loads(capsys.readouterr().out)["kill"] is True


def test_mcp_stdio_roundtrip():
    """Spawns the real server and drives it with the SDK client (scripts/smoke_mcp.py)."""
    p = subprocess.run([sys.executable, str(ROOT / "scripts" / "smoke_mcp.py")], capture_output=True, text=True, timeout=120,
                       env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
    assert p.returncode == 0, p.stdout + p.stderr
    assert "SMOKE OK" in p.stdout
    assert "score_job" in p.stdout and "rate_calculator" in p.stdout
