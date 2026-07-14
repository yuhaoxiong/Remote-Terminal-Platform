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


def test_deploy_workflow_bootstrap_does_not_depend_on_global_tmp() -> None:
    workflow = (ROOT / ".github/workflows/deploy.yml").read_text(encoding="utf-8")

    assert 'DEPLOY_TMP_DIR="${HOME:?remote HOME is not set}/.cache/edge-platform-deploy"' in workflow
    assert 'mkdir -p "$DEPLOY_TMP_DIR"' in workflow
    assert 'chmod 700 "$DEPLOY_TMP_DIR"' in workflow
    assert 'mktemp "$DEPLOY_TMP_DIR/deploy.XXXXXXXXXX"' in workflow
    assert 'DEPLOY_SCRIPT="$(mktemp)"' not in workflow
