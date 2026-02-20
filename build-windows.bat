@echo off
chcp 65001 >nul
echo ========================================
echo   EPUB 工具箱 Windows 一键打包脚本
echo ========================================
echo.

:: 检查依赖
where python >nul 2>&1 || (echo [错误] 未找到 python，请先安装 Python 3 && exit /b 1)
where go >nul 2>&1 || (echo [错误] 未找到 go，请先安装 Go && exit /b 1)
where wails >nul 2>&1 || (echo [错误] 未找到 wails CLI，请运行: go install github.com/wailsapp/wails/v2/cmd/wails@latest && exit /b 1)

:: Step 1: 用 PyInstaller 编译 Python 后端
echo [1/3] 编译 Python 后端...
cd backend-py
pip install -r requirements.txt -q
pip install pyinstaller -q
pyinstaller --onefile --name converter-backend main.py -y --clean
if errorlevel 1 (echo [错误] PyInstaller 编译失败 && exit /b 1)

:: 复制到 backend-bin
echo [2/3] 复制后端到 backend-bin...
cd ..
if not exist backend-bin mkdir backend-bin
copy /Y backend-py\dist\converter-backend.exe backend-bin\converter-backend.exe

:: Step 3: Wails 编译
echo [3/3] 编译 Wails 应用...
wails build -platform windows/amd64
if errorlevel 1 (echo [错误] Wails 编译失败 && exit /b 1)

:: 组装发布目录
echo.
echo 组装发布包...
if exist release rmdir /s /q release
mkdir release
copy /Y build\bin\epub-tool-go.exe release\epub-tool-go.exe
mkdir release\backend-bin
copy /Y backend-bin\converter-backend.exe release\backend-bin\converter-backend.exe

echo.
echo ========================================
echo   打包完成！发布目录: release\
echo   epub-tool-go.exe + backend-bin\converter-backend.exe
echo ========================================
