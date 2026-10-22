@echo off
chcp 65001 >nul
title YZL 启动器 - 一键打包
cd /d "%~dp0"
echo [1/3] 安装依赖...
python -m pip install -r requirements.txt pyinstaller --quiet || goto :err
echo [2/3] 打包程序...
python -m PyInstaller --noconfirm --clean --onefile --windowed --name "YZL启动器" --icon assets\icon.ico main.py || goto :err
echo [3/3] 生成独立安装包...
set "ISCC="
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files\Inno Setup 6\ISCC.exe" set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"
if defined ISCC (
  "%ISCC%" YZLLauncher.iss
) else (
  echo 未检测到 Inno Setup，dist\YZL启动器.exe 已是独立可执行文件。
)
echo 完成！产物在 dist 目录。
pause
exit /b 0
:err
echo 打包失败，请检查输出。
pause
exit /b 1
