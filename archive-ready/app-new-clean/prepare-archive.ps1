$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$root = $PSScriptRoot
$out = Join-Path $root "archive-ready"
$pkg = Join-Path $out "app-new-clean"
$zip = Join-Path $out "app-new-clean.zip"

Write-Host "Preparing clean archive package..." -ForegroundColor Cyan

if (Test-Path $pkg) {
    Remove-Item $pkg -Recurse -Force
}

New-Item -ItemType Directory -Path $pkg -Force | Out-Null

$excludeDirs = @(
    ".git",
    ".venv",
    ".venv-1",
    "node_modules",
    "client-new\node_modules",
    "client-new\dist",
    "client-new\playwright-report",
    "client-new\test-results",
    "client-new\blob-report",
    "backups",
    "archive-ready",
    "ssl"
)

$excludeFiles = @(
    ".env",
    "server\.env",
    "*.pyc"
)

$robocopyArgs = @($root, $pkg, "/E")
$excludeDirs | ForEach-Object { $robocopyArgs += @("/XD", $_) }
$excludeFiles | ForEach-Object { $robocopyArgs += @("/XF", $_) }

& robocopy @robocopyArgs | Out-Null

Get-ChildItem $pkg -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Get-ChildItem $pkg -Recurse -Include "*.pyc" -File -ErrorAction SilentlyContinue |
    Remove-Item -Force -ErrorAction SilentlyContinue

if (Test-Path $zip) {
    Remove-Item $zip -Force
}

Compress-Archive -Path (Join-Path $pkg "*") -DestinationPath $zip -Force

Write-Host "Done." -ForegroundColor Green
Write-Host "Folder: $pkg" -ForegroundColor Green
Write-Host "ZIP:    $zip" -ForegroundColor Green
