@echo off
REM =============================================================================
REM build.bat — Script de build para Windows
REM =============================================================================
REM Uso: Abrir Prompt de Comando como Administrador e executar build.bat
REM
REM Dependências do sistema:
REM   Python 3.10+ com tkinter incluído (python.org/downloads)
REM   UPX (opcional, para compressão): https://upx.github.io/
REM =============================================================================

setlocal EnableDelayedExpansion

set APP_NAME=Documentador
set VERSION=1.0.0

echo ==================================================
echo   Build: %APP_NAME% v%VERSION%
echo   Plataforma: Windows
echo ==================================================

REM 1. Criar ambiente virtual se não existir
if not exist "venv\" (
    echo [1/4] Criando ambiente virtual...
    python -m venv venv
)

echo [1/4] Ativando ambiente virtual e instalando dependencias...
call venv\Scripts\activate.bat
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt
python -m pip install --quiet pyinstaller

REM 2. Limpar builds anteriores
echo [2/4] Limpando builds anteriores...
if exist "dist\" rmdir /s /q dist
if exist "build\" rmdir /s /q build

REM 3. Executar PyInstaller
echo [3/4] Executando PyInstaller...
pyinstaller documentador.spec --noconfirm --clean

REM 4. Verificar e renomear saída
echo [4/4] Verificando saida...

if exist "dist\Documentador.exe" (
    echo     Executavel gerado: dist\Documentador.exe
    
    REM Renomear com versão
    copy "dist\Documentador.exe" "dist\%APP_NAME%-%VERSION%-Windows.exe" > nul
    echo     Copia com versao: dist\%APP_NAME%-%VERSION%-Windows.exe
) else (
    echo     ERRO: Executavel nao encontrado em dist\Documentador.exe
    exit /b 1
)

echo.
echo Build concluido com sucesso!
echo Arquivos em dist\:
dir /b dist\
