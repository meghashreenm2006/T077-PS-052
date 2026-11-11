@echo off
 title T077-PS-052 - Cold Chain Compliance Engine
 echo ==============================================
 echo   T077-PS-052 - TEST AND RUN PROJECT
 echo ==============================================
 echo.
 echo [1/2] Running automated tests...
 python -m unittest discover -s tests -v
 if errorlevel 1 (
   echo.
   echo TESTS FAILED. Please share a screenshot of this window.
   pause
   exit /b 1
 )
 echo.
 echo [2/2] Running complete sample shipment pipeline...
 python run_project.py
 if errorlevel 1 (
   echo.
   echo PIPELINE FAILED. Please share a screenshot of this window.
   pause
   exit /b 1
 )
 echo.
 echo SUCCESS: tests and sample pipeline completed.
 echo Open the output folder to view the five CSV reports.
 pause
