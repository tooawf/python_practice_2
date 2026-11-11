@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="test" goto test
if "%~1"=="demo" goto demo
python -m png_gif.server %*
exit /b %errorlevel%
:test
python -m pytest
exit /b %errorlevel%
:demo
python examples\demo.py
exit /b %errorlevel%
