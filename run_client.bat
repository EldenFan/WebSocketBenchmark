@echo off
chcp 65001 >nul

echo --- Сборка проекта ---
cd TestLauncher
dotnet build TestLauncher.csproj --configuration Release
if %errorlevel% neq 0 (
    echo [ОШИБКА] Сборка проекта не удалась.
    pause
    exit /b
)
echo Проект успешно собран.
echo.

echo --- Настройка параметров теста ---
echo Доступные сетевые интерфейсы:
tshark -D
echo.

set /p interface="Введите индекс интерфейса (из списка выше): "
set /p ip="Введите IP сервера (по умолчанию 127.0.0.1): "
if "%ip%"=="" set ip=127.0.0.1

set /p port="Введите порт (по умолчанию 5000): "
if "%port%"=="" set port=5000

echo.
echo Запуск тестов...
echo.

bin\Release\net8.0\TestLauncher.exe %interface% %ip% %port%

echo.
echo Тестирование завершено.
pause