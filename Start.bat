@echo off
start "Lavalink Audio Server" cmd /k "cd lavalink && java -jar Lavalink.jar"
timeout /t 5 /nobreak >nul
start "Discord Music Bot" cmd /k "python main.py"