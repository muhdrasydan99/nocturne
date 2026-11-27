@echo off
cd /d "%~dp0"

if not exist .venv py -m venv .venv || goto :fail
call .venv\Scripts\activate.bat || goto :fail
python -m pip install --upgrade pip
python -m pip install PySide6 numpy librosa pyinstaller || goto :fail

python make_icon.py || goto :fail

pyinstaller --noconfirm --clean --windowed --onedir --name Nocturne ^
  --contents-directory "." --icon nocturne.ico ^
  --collect-all librosa --hidden-import lyric_engine ^
  main.py || goto :fail

rem Salin fail tambahan (kalau ada) ke sebelah Nocturne.exe
if exist fonts xcopy fonts dist\Nocturne\fonts\ /E /I /Y >nul
for %%F in (nocturne_icon.png nocturne_icon_exact.jpg icon.png ffmpeg.exe) do if exist %%F copy /Y %%F dist\Nocturne\ >nul

echo.
echo SIAP: dist\Nocturne\Nocturne.exe
pause
exit /b 0

:fail
echo.
echo BUILD GAGAL. Copy teks error di atas.
pause
exit /b 1
