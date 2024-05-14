@echo off

for /f "tokens=3" %%i in (_version.py) do set version=%%i

if not exist Release\. md Release
7z a -tzip -r release\DirHotList.%version%.zip *.py *.lng *.hlf *.md *.xml *.txt
