# ============================================================
# Agile Business — Утилита бэкапа и восстановления БД (Windows)
#
# Использование:
#   .\db-backup.ps1                     — создать бэкап
#   .\db-backup.ps1 -Restore FILE       — восстановить из файла
#   .\db-backup.ps1 -List               — список бэкапов
#   .\db-backup.ps1 -Clean [DAYS]       — удалить старые (по умолчанию 30)
# ============================================================

param(
    [string]$Restore,
    [switch]$List,
    [int]$Clean = 0,
    [switch]$Help
)

$ErrorActionPreference = "Stop"

$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$BACKUP_DIR = Join-Path $ROOT "backups"
if (-not (Test-Path $BACKUP_DIR)) { New-Item -ItemType Directory -Path $BACKUP_DIR | Out-Null }

# ——— Загружаем .env ———

$envFile = Join-Path $ROOT "server\.env"
if (-not (Test-Path $envFile)) { $envFile = Join-Path $ROOT ".env" }

$DB_USER = "agile"
$DB_NAME = "agile_db"
$DB_HOST = "localhost"
$DB_PORT = "5432"
$DB_PASSWORD = "agile_pass"

if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            $key = $Matches[1].Trim()
            $val = $Matches[2].Trim()
            switch ($key) {
                "DB_USER"     { $DB_USER = $val }
                "DB_NAME"     { $DB_NAME = $val }
                "DB_HOST"     { $DB_HOST = $val }
                "DB_PORT"     { $DB_PORT = $val }
                "DB_PASSWORD" { $DB_PASSWORD = $val }
            }
        }
    }
}

# ——— Функции ———

function Do-Backup {
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $filename = "agile_db_${timestamp}.sql"
    $filepath = Join-Path $BACKUP_DIR $filename
    $gzpath = "${filepath}.gz"

    Write-Host "Создание бэкапа..." -ForegroundColor Cyan

    $env:PGPASSWORD = $DB_PASSWORD
    pg_dump -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME `
        --no-owner --no-acl --clean --if-exists `
        -f $filepath

    # Сжимаем — используем .NET GZip
    $bytes = [System.IO.File]::ReadAllBytes($filepath)
    $outStream = [System.IO.File]::Create($gzpath)
    $gzipStream = New-Object System.IO.Compression.GZipStream($outStream, [System.IO.Compression.CompressionMode]::Compress)
    $gzipStream.Write($bytes, 0, $bytes.Length)
    $gzipStream.Close()
    $outStream.Close()
    Remove-Item $filepath

    $size = "{0:N2} MB" -f ((Get-Item $gzpath).Length / 1MB)
    Write-Host "[OK] Бэкап создан: $(Split-Path $gzpath -Leaf) ($size)" -ForegroundColor Green
}

function Do-Restore($file) {
    # Ищем файл
    if (-not (Test-Path $file)) {
        $tryPath = Join-Path $BACKUP_DIR $file
        if (Test-Path $tryPath) { $file = $tryPath }
        else {
            Write-Host "Файл не найден: $file" -ForegroundColor Red
            exit 1
        }
    }

    Write-Host "ВНИМАНИЕ: Восстановление перезапишет текущую БД!" -ForegroundColor Yellow
    Write-Host "Файл: $(Split-Path $file -Leaf)" -ForegroundColor Cyan
    $confirm = Read-Host "Продолжить? (y/N)"
    if ($confirm -ne "y" -and $confirm -ne "Y") {
        Write-Host "Отменено."
        return
    }

    Write-Host "Восстановление БД..." -ForegroundColor Cyan

    # Распаковываем
    $tempSql = Join-Path $env:TEMP "agile_restore_$(Get-Date -Format 'yyyyMMdd_HHmmss').sql"
    $inStream = [System.IO.File]::OpenRead($file)
    $gzipStream = New-Object System.IO.Compression.GZipStream($inStream, [System.IO.Compression.CompressionMode]::Decompress)
    $outStream = [System.IO.File]::Create($tempSql)
    $gzipStream.CopyTo($outStream)
    $gzipStream.Close()
    $inStream.Close()
    $outStream.Close()

    $env:PGPASSWORD = $DB_PASSWORD
    psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -q -f $tempSql 2>$null

    Remove-Item $tempSql
    Write-Host "[OK] БД восстановлена из $(Split-Path $file -Leaf)" -ForegroundColor Green
    Write-Host "Рекомендуется перезапустить бэкенд" -ForegroundColor Yellow
}

function Do-List {
    Write-Host "Список бэкапов:" -ForegroundColor Cyan
    Write-Host ""

    $files = Get-ChildItem $BACKUP_DIR -Filter "agile_db_*.sql.gz" -ErrorAction SilentlyContinue | Sort-Object Name
    if ($files.Count -eq 0) {
        Write-Host "  Бэкапов нет" -ForegroundColor Yellow
        return
    }

    foreach ($f in $files) {
        $size = "{0:N2} MB" -f ($f.Length / 1MB)
        $dateStr = $f.Name -replace 'agile_db_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})\.sql\.gz', '$1-$2-$3 $4:$5:$6'
        Write-Host "  $($f.Name)  ($size)  $dateStr" -ForegroundColor Green
    }
    Write-Host ""
    Write-Host "  Всего: $($files.Count)"
}

function Do-Clean($days) {
    $cutoff = (Get-Date).AddDays(-$days)
    Write-Host "Удаление бэкапов старше $days дней..." -ForegroundColor Cyan

    $files = Get-ChildItem $BACKUP_DIR -Filter "agile_db_*.sql.gz" |
             Where-Object { $_.LastWriteTime -lt $cutoff }

    if ($files.Count -eq 0) {
        Write-Host "  Нечего удалять" -ForegroundColor Green
        return
    }

    foreach ($f in $files) {
        Remove-Item $f.FullName
        Write-Host "  Удалён: $($f.Name)" -ForegroundColor Yellow
    }
    Write-Host "Удалено: $($files.Count)" -ForegroundColor Green
}

function Show-Help {
    Write-Host "Agile Business — Утилита бэкапа БД (Windows)" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  .\db-backup.ps1                  Создать бэкап"
    Write-Host "  .\db-backup.ps1 -Restore ФАЙЛ    Восстановить из файла"
    Write-Host "  .\db-backup.ps1 -List             Список бэкапов"
    Write-Host "  .\db-backup.ps1 -Clean 30         Удалить старые бэкапы"
    Write-Host "  .\db-backup.ps1 -Help             Эта справка"
}

# ——— Точка входа ———

if ($Help) { Show-Help; return }
if ($List) { Do-List; return }
if ($Clean -gt 0) { Do-Clean $Clean; return }
if ($Restore) { Do-Restore $Restore; return }

# По умолчанию — бэкап
Do-Backup
