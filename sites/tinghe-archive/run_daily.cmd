@echo off
chcp 65001 >nul
cd /d "D:\视频创作\ace-video-kingdom\sites\tinghe-archive"
"C:\Users\Administrator\.local\bin\opencode.exe" run --auto --file "D:\视频创作\ace-video-kingdom\sites\tinghe-archive\DAILY_DIRECTIVE.md" "严格执行附件作战指令，完成今天域外星际原创桌批次，输出末行 JSON 摘要。" >> "D:\视频创作\ace-video-kingdom\sites\tinghe-archive\daily_run.log" 2>&1
