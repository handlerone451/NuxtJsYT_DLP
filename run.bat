@echo off
:: Jalankan npm run dev di terminal aktif
start powershell.exe -NoExit -Command "npm run start"

:: Tunggu sejenak untuk memastikan server pertama berjalan
timeout /t 5 >nul

:: Buka tab baru di Windows Terminal dan jalankan perintah python
start wt -w 0 nt -d ./server powershell.exe -NoExit -Command "python .\youtubeDownloader.py"
