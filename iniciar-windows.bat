@echo off
setlocal
cd /d "%~dp0"
title NJA System - Inicializacao
if exist configuracao-local.bat call configuracao-local.bat
call :main
set "NJA_RESULT=%errorlevel%"
echo.
if not "%NJA_RESULT%"=="0" echo Nao foi possivel iniciar. Envie uma foto desta janela.
echo Esta janela permanecera aberta para voce conferir as mensagens.
pause
exit /b %NJA_RESULT%

:main
echo NJA System - Preparando o sistema...
echo Pasta: %CD%
echo.
set "NJA_PY="
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)" >nul 2>nul
if not errorlevel 1 set "NJA_PY=py -3"
if defined NJA_PY goto python_ready
python -c "import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)" >nul 2>nul
if not errorlevel 1 set "NJA_PY=python"
if defined NJA_PY goto python_ready
echo Python 3.12 ou superior nao foi encontrado.
echo Instale o Python, habilite Add python.exe to PATH e execute novamente.
exit /b 1

:python_ready
if exist ".venv\Scripts\python.exe" goto environment_ready
echo Criando o ambiente Python...
%NJA_PY% -m venv .venv > inicializacao.log 2>&1
if not errorlevel 1 goto environment_ready
type inicializacao.log
exit /b 1

:environment_ready
".venv\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)" >nul 2>nul
if not errorlevel 1 goto dependencies
echo O ambiente .venv usa uma versao antiga ou esta incompleto.
echo Renomeie a pasta .venv para .venv-antiga e execute novamente.
exit /b 1

:dependencies
".venv\Scripts\python.exe" -c "from PIL import Image; import tzdata; import cryptography" >nul 2>nul
if not errorlevel 1 goto account
echo Instalando suporte a fotos e fuso horario. Aguarde...
".venv\Scripts\python.exe" -m pip install Pillow tzdata cryptography > inicializacao.log 2>&1
if not errorlevel 1 goto account
type inicializacao.log
echo Verifique sua conexao com a internet.
exit /b 1

:account
".venv\Scripts\python.exe" -c "from app import init,connect; init(); c=connect(); exit(0 if c.execute('select 1 from users where master=1').fetchone() else 2)" > inicializacao.log 2>&1
set "NJA_ACCOUNT_STATUS=%errorlevel%"
if "%NJA_ACCOUNT_STATUS%"=="0" goto launch
if "%NJA_ACCOUNT_STATUS%"=="2" goto create_master
type inicializacao.log
exit /b 1

:create_master
echo Crie sua conta master. A senha nao aparece enquanto voce digita.
".venv\Scripts\python.exe" manage.py init-master
if errorlevel 1 exit /b 1

:launch
echo Abrindo servidor e alertas...
start "NJA System" cmd /k ""%CD%\.venv\Scripts\python.exe" "%CD%\app.py""
start "NJA Alertas" cmd /k ""%CD%\.venv\Scripts\python.exe" "%CD%\scheduler.py""
echo Aguardando o servidor responder...
".venv\Scripts\python.exe" abrir_navegador.py
if errorlevel 1 exit /b 1
echo Sistema aberto em http://localhost:8000
echo Mantenha as janelas NJA System e NJA Alertas abertas.
exit /b 0
