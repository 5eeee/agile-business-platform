Set-Location $PSScriptRoot
Get-Content .env | ForEach-Object {
    if ($_ -match '^([^#][^=]*)=(.*)$') {
        [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim())
    }
}
python -c "import uvicorn; uvicorn.run('app.main:app', host='0.0.0.0', port=8000)"
