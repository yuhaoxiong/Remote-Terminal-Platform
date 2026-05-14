param(
    [string]$InstallRoot = "/opt/edge-platform",
    [string]$ServiceUser = "edge-platform",
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

Write-Host "Installing backend into $InstallRoot"
python -m venv "$InstallRoot/.venv"
& "$InstallRoot/.venv/Scripts/python.exe" -m pip install --upgrade pip
& "$InstallRoot/.venv/Scripts/python.exe" -m pip install -r "$InstallRoot/backend/requirements.txt"

$service = @"
[Unit]
Description=AI Edge Platform FastAPI backend
After=network.target

[Service]
User=$ServiceUser
WorkingDirectory=$InstallRoot/backend
Environment=PYTHONPATH=$InstallRoot/backend
ExecStart=$InstallRoot/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port $Port
Restart=always

[Install]
WantedBy=multi-user.target
"@

$service | Set-Content -Path "$InstallRoot/edge-platform.service" -Encoding UTF8
Write-Host "Generated systemd service and installed requirements.txt dependencies for uvicorn."
