@echo off
SETLOCAL EnableDelayedExpansion

echo ========================================================
echo NuPredictor: Iniciando Entorno de Validacion
echo ========================================================

:: 1. Verificar Conda
where conda >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Conda no detectado. Asegurate de tenerlo instalado.
    exit /b 1
)

:: 2. Crear Entorno si no existe (opcional, aqui lo asumimos creado o lo forzamos)
echo [1/3] Verificando entorno 'nu'...
call conda activate nu >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [INFO] Creando entorno 'nu' con Python 3.11...
    call conda create -n nu python=3.11 -y
    call conda activate nu
)

:: 3. Instalar dependencias
echo [2/3] Verificando dependencias...
pip install -r requirements.txt --quiet

:: 4. Ejecutar validacion
echo [3/3] Ejecutando Validacion del Parser...
python validate_parser.py

echo ========================================================
echo Validacion Finalizada.
pause
