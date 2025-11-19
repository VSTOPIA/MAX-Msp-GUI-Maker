@echo off
REM Helper script to create/activate venv, install requirements, and run the GUI (Windows CMD).

cd /d %~dp0
echo Using project directory: %cd%

IF NOT EXIST .venv (
  echo Creating virtual environment (.venv)...
  python -m venv .venv
)

echo Activating virtual environment...
call .venv\Scripts\activate.bat

echo Upgrading pip and installing requirements (including PyQt6)...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo Starting GUI...
python gui.py


