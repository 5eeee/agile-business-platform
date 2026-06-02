@echo off
cd /d e:\agile-workspace\server
for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
    echo %%a | findstr /b "#" >nul || set "%%a=%%b"
)
python -c "import uvicorn; uvicorn.run('app.main:app', host='0.0.0.0', port=8000)"
