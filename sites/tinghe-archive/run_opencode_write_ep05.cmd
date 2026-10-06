@echo off
chcp 65001 >nul
set PATH=%PATH%;C:\Program Files\nodejs
cd /d "D:\视频创作\ace-video-kingdom\sites\tinghe-archive"

"C:\Users\Administrator\.local\bin\opencode.exe" run --auto --file DAILY_DIRECTIVE.md --file build_context_bundle.py --file build_originals.py --file run_audit.py --file AUDIT_PROMPT.md --file originals_source/fanguan/context_bundle.md --file originals_source/liufang/context_bundle.md --file originals_source/tingjijia/context_bundle.md --file originals_source/tuiqun/context_bundle.md --file originals_source/zhenqianjin/context_bundle.md "为 5 部作品各写第 5 集 (ep05)，只在 work.json 的 episodes 里追加 blocks。每集：scene(含 place/time/light)、cast(在场/未出场)、若干 para/line、结尾唯一 hook。beat 必须是可视化的剧情推进。输出末行 JSON 摘要。" >> daily_run.log 2>&1