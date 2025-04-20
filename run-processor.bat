@echo off
set LOGFILE=processor_%DATE:~-4%%DATE:~-7,2%%DATE:~-10,2%_%TIME:~0,2%%TIME:~3,2%.log
echo Starting processor at %TIME% > %LOGFILE%
python processor.py %* 2>&1 >> %LOGFILE%
echo Finished at %TIME% >> %LOGFILE%