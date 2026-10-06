@echo off
chcp 65001 >nul
cd /d D:\视频创作\ace-video-kingdom\sites\tinghe-archive
C:\Users\Administrator\.local\bin\opencode.exe run --auto --file DAILY_DIRECTIVE.md "为 5 部作品各写第 5 集 (ep05)，只在 work.json 的 episodes 里追加 blocks。每集：scene、cast、若干 para/line、结尾唯一 hook。beat 必须是可视化的剧情推进。输出末行 JSON 摘要。" >> daily_run.log 2>&1