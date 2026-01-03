@echo off
REM Proxy Server - Quick Commands

if "%1"=="" goto help
if "%1"=="start" goto start
if "%1"=="test" goto test
if "%1"=="logs" goto logs
if "%1"=="clean" goto clean
goto help

:help
echo.
echo Proxy Server - Available Commands
echo ==================================
echo.
echo   run.bat start    - Start the proxy server
echo   run.bat test     - Run test suite
echo   run.bat logs     - Show recent logs
echo   run.bat clean    - Clean log files
echo.
goto end

:start
echo Starting proxy server...
python src/proxy_server.py --host 127.0.0.1 --port 8888 --blacklist config/blocked_domains.txt --log-dir logs
goto end

:test
echo Running tests...
echo Make sure proxy server is running in another terminal!
echo.
python tests/test_manual.py
goto end

:logs
echo Recent Access Logs:
echo ===================
type logs\access.log
echo.
echo Recent Error Logs:
echo ==================
type logs\error.log 2>nul
goto end

:clean
echo Cleaning logs...
if exist logs rmdir /s /q logs
mkdir logs
echo Logs cleaned!
goto end

:end
