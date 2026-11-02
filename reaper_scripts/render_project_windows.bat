@echo off
REM Set REAPER_EXE below if reaper.exe is not on PATH.
set "REAPER_EXE=reaper.exe"
if "%~1"=="" (
  echo Usage: render_project_windows.bat "C:\path\to\project.rpp"
  exit /b 2
)
"%REAPER_EXE%" -renderproject "%~1"
