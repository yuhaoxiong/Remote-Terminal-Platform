from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_wave6_deployment_assets_are_present() -> None:
    expected_files = {
        "scripts/deploy/install_backend.ps1": ["python", "requirements.txt", "uvicorn"],
        "scripts/deploy/edge_bootstrap.sh": ["frpc", "ssh", "vnc"],
        "scripts/deploy/backup_sqlite.ps1": ["platform.db", "backup"],
        "docs/deployment.md": ["SQLite", "systemd", "Nginx", "backup"],
    }

    for relative_path, required_terms in expected_files.items():
        path = ROOT / relative_path
        assert path.exists(), f"missing {relative_path}"
        content = path.read_text(encoding="utf-8")
        for term in required_terms:
            assert term in content
