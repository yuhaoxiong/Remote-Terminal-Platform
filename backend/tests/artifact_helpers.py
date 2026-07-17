from __future__ import annotations

import io
import tarfile


REQUIRED_PACKAGE_FILES = {
    "artifacts/app.py": b"print('ok')\n",
    "config/default.yaml": b"camera: 0\n",
    "config/collect-schema.json": b'{"type":"object"}\n',
    "scripts/preflight.sh": b"#!/bin/sh\nexit 0\n",
    "scripts/install.sh": b"#!/bin/sh\nexit 0\n",
    "scripts/configure.sh": b"#!/bin/sh\nexit 0\n",
    "scripts/start.sh": b"#!/bin/sh\nexit 0\n",
    "scripts/healthcheck.sh": b'#!/bin/sh\necho \'{"status":"healthy"}\'\n',
    "scripts/collect.sh": b"#!/bin/sh\nexit 0\n",
    "scripts/rollback.sh": b"#!/bin/sh\nexit 0\n",
    "scripts/uninstall.sh": b"#!/bin/sh\nexit 0\n",
    "systemd/service.template": b"[Service]\nExecStart=/bin/true\n",
}


def build_standard_package(
    function_code: str,
    version: str,
    profile_code: str,
    *,
    omit_paths: set[str] | None = None,
    artifact_content: bytes | None = None,
) -> bytes:
    manifest = (
        "schema_version: 1\n"
        f"function_code: {function_code}\n"
        f"version: {version}\n"
        f"hardware_profile: {profile_code}\n"
        "runtime: python-venv-systemd\n"
    ).encode()
    files = {"manifest.yaml": manifest, **REQUIRED_PACKAGE_FILES}
    if artifact_content is not None:
        files["artifacts/app.py"] = artifact_content
    for path in omit_paths or set():
        files.pop(path, None)
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for path, content in files.items():
            info = tarfile.TarInfo(name=f"{function_code}-{version}-{profile_code}/{path}")
            info.size = len(content)
            info.mode = 0o755 if path.startswith("scripts/") else 0o644
            archive.addfile(info, io.BytesIO(content))
    return buffer.getvalue()
