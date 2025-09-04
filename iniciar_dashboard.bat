@echo off
echo ============================================
echo 🚀 Iniciando Dashboard de Agua en Docker
echo ============================================

REM Detener contenedor viejo en 8503
for /f "tokens=*" %%i in ('docker ps -q --filter "publish=8503"') do docker stop %%i

REM Correr el contenedor ya construido
start cmd /k "cd C:\dashboard_agua && docker run -p 8503:8501 dashboard-agua"

REM Esperar unos segundos
timeout /t 10

REM Lanzar ngrok en otra ventana
start cmd /k "cd C:\Users\jcruzm\Downloads\ngrok-v3-stable-windows-amd64 && ngrok http 8503"

echo ============================================
echo ✅ Dashboard disponible en http://localhost:8503
echo ✅ Enlace público se mostrará en la ventana de Ngrok
echo ============================================
pause
