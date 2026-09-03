@echo off
chcp 65001 > nul
title Page FB - Quet Tinh Trang & Loi Dang Bai BlogB
cd /d "%~dp0"
echo =====================================================================
echo    KHOI DONG CONG CU SOAT LOI DANG BAI THEO NGAY (BLOGB)
echo =====================================================================
echo.
echo Dang mo giao dien cong cu...
python post_status_scanner.py
if errorlevel 1 (
    echo.
    echo [LOI] Da xay ra loi khi khoi chay.
    pause
)
