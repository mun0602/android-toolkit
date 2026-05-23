@echo off
title Khởi chạy Android Farm Controller Pro
chcp 65001 >nul
cd /d "%~dp0"
echo =======================================================
echo    KHỞI CHẠY ANDROID Farm Controller Pro v1.2
echo =======================================================
echo.

:: 1. Ưu tiên dùng môi trường ảo .venv cục bộ nếu tồn tại
if exist ".venv\Scripts\python.exe" (
    echo [OK] Phát hiện môi trường ảo .venv cục bộ.
    echo Đang khởi chạy ứng dụng...
    start "" ".venv\Scripts\python.exe" main.py
    exit /b
)

:: 2. Kiểm tra xem python trong PATH có hoạt động không
python --version >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Phát hiện Python hệ thống từ biến môi trường PATH.
    echo Đang khởi chạy ứng dụng...
    start "" python main.py
    exit /b
)

:: 3. Nếu không tìm thấy python, thử chạy bằng đường dẫn Python lúc ghi nhận
if exist "D:\code\android-toolkit\.venv\Scripts\python.exe" (
    echo [OK] Khởi chạy bằng đường dẫn Python lúc ghi nhận: "D:\code\android-toolkit\.venv\Scripts\python.exe"
    start "" "D:\code\android-toolkit\.venv\Scripts\python.exe" main.py
    exit /b
)

echo [LỖI] Không tìm thấy trình thông dịch Python phù hợp trên máy!
echo Vui lòng cài đặt Python và tích chọn "Add Python to PATH" lúc cài đặt.
echo.
pause
