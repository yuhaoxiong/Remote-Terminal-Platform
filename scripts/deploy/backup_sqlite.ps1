param(
    [string]$DatabasePath = "backend/data/platform.db",
    [string]$BackupRoot = "backups"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $DatabasePath)) {
    throw "platform.db not found at $DatabasePath"
}

New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupPath = Join-Path $BackupRoot "platform-$stamp.db"
Copy-Item -LiteralPath $DatabasePath -Destination $backupPath -Force
Write-Host "backup created: $backupPath"
