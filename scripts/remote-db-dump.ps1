#Requires -Version 5.1
<#
.SYNOPSIS
  Дамп PostgreSQL на удалённом сервере через SSH и сохранение в backups/ проекта.

.DESCRIPTION
  Запускайте на СВОЕМ ПК, где уже работает: ssh user@host (ключ в ssh-agent или -IdentityFile).
  Режим по умолчанию: на сервере в каталоге репозитория выполняется
    docker compose exec -T db pg_dump ...
  (как в docker-compose.yml: agile_user / agile_workspace).

.EXAMPLE
  $env:REMOTE_PG_PASSWORD = 'пароль_из_серверного_.env_DB_PASSWORD'
  .\scripts\remote-db-dump.ps1 -SshTarget deploy@203.0.113.10 -RemoteRepoPath /home/deploy/agile_workspace

.EXAMPLE
  .\scripts\remote-db-dump.ps1 -SshTarget deploy@my.vps -RemoteRepoPath /var/www/agile -IdentityFile ~\.ssh\id_ed25519 -PgPassword 'secret'

.NOTES
  Агент в Cursor не может подключиться к вашему VPS без ваших ключей — скрипт для локального запуска.
#>
param(
    [Parameter(Mandatory = $true)]
    [string] $SshTarget,

    [Parameter(Mandatory = $true)]
    [string] $RemoteRepoPath,

    [string] $IdentityFile,
    [string] $ComposeFile = "docker-compose.yml",
    [string] $DbServiceName = "db",
    [string] $PgUser = "agile_user",
    [string] $PgDatabase = "agile_workspace",
    [string] $PgPassword,
    [switch] $UseDockerComposeV1
)

function Escape-SshSingleQuoted {
    param([string] $s)
    if ($null -eq $s) { return "''" }
    $escaped = $s -replace "'", "'\''"
    return "'$escaped'"
}

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$BackupDir = Join-Path $ProjectRoot "backups"
if (-not (Test-Path $BackupDir)) {
    New-Item -ItemType Directory -Path $BackupDir | Out-Null
}

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$LocalFile = Join-Path $BackupDir "remote_${ts}.sql"

if (-not $PgPassword -and $env:REMOTE_PG_PASSWORD) {
    $PgPassword = $env:REMOTE_PG_PASSWORD
}

$compose = if ($UseDockerComposeV1) { "docker-compose" } else { "docker compose" }

$dumpFlags = "-U $PgUser -d $PgDatabase --no-owner --no-acl --clean --if-exists"

if ($PgPassword) {
    $remoteInner = @(
        "cd $(Escape-SshSingleQuoted $RemoteRepoPath)",
        "&& $compose -f $(Escape-SshSingleQuoted $ComposeFile) exec -T -e PGPASSWORD=$(Escape-SshSingleQuoted $PgPassword) $DbServiceName pg_dump $dumpFlags"
    ) -join " "
}
else {
    $remoteInner = @(
        "cd $(Escape-SshSingleQuoted $RemoteRepoPath)",
        "&& $compose -f $(Escape-SshSingleQuoted $ComposeFile) exec -T $DbServiceName pg_dump $dumpFlags"
    ) -join " "
}

$remoteCmd = "bash -lc $(Escape-SshSingleQuoted $remoteInner)"

$sshArgList = @()
if ($IdentityFile) {
    $resolved = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($IdentityFile)
    $sshArgList += "-i", $resolved
}
$sshArgList += $SshTarget, $remoteCmd

Write-Host "SSH: $SshTarget" -ForegroundColor Cyan
Write-Host "Remote: $RemoteRepoPath  ($compose exec $DbServiceName pg_dump ...)" -ForegroundColor Cyan
Write-Host "Local: $LocalFile" -ForegroundColor Cyan

$tmpErr = Join-Path $env:TEMP "remote-db-dump-$PID.err"
Remove-Item $tmpErr -ErrorAction SilentlyContinue
$p = Start-Process -FilePath "ssh" -ArgumentList $sshArgList -Wait -PassThru -NoNewWindow `
    -RedirectStandardOutput $LocalFile -RedirectStandardError $tmpErr

$stderr = if (Test-Path $tmpErr) { Get-Content -LiteralPath $tmpErr -Raw -Encoding UTF8 } else { "" }
Remove-Item $tmpErr -ErrorAction SilentlyContinue

if ($p.ExitCode -ne 0) {
    if (-not [string]::IsNullOrWhiteSpace($stderr)) { Write-Host $stderr -ForegroundColor Red }
    throw ('ssh/pg_dump failed (exit {0}). Check RemoteRepoPath, docker compose, DB service; use -PgPassword or $env:REMOTE_PG_PASSWORD.' -f $p.ExitCode)
}

$stdoutLen = (Get-Item -LiteralPath $LocalFile -ErrorAction SilentlyContinue).Length
if (-not $stdoutLen -or $stdoutLen -lt 100) {
    throw 'Dump missing or too small. See stderr above; set PGPASSWORD (-PgPassword or REMOTE_PG_PASSWORD) if pg_dump needs it in the container.'
}
$mb = [math]::Round((Get-Item $LocalFile).Length / 1MB, 2)
Write-Host ('[OK] Saved: {0} ({1} MB)' -f $LocalFile, $mb) -ForegroundColor Green
