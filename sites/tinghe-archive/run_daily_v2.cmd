@echo off
chcp 65001 >nul
set PATH=%PATH%;C:\Program Files\nodejs
cd /d "D:\视频创作\ace-video-kingdom\sites\tinghe-archive"

rem 1. Generate context bundles for all works
py -3 build_context_bundle.py fanguan
py -3 build_context_bundle.py liufang
py -3 build_context_bundle.py tingjijia
py -3 build_context_bundle.py tuiqun
py -3 build_context_bundle.py zhenqianjin

rem 2. Run opencode to write ONE new episode (ep05) per work
"C:\Users\Administrator\.local\bin\opencode.exe" run --auto --file "DAILY_DIRECTIVE.md" --file "build_context_bundle.py" --file "build_originals.py" --file "run_audit.py" --file "AUDIT_PROMPT.md" "为每个已有作品各写一集第5集(ep05)，只在 work.json 的 episodes 里追加 blocks，不改动已有内容。严格遵循 DAILY_DIRECTIVE.md 的结构要求：每集必须含 scene/cast/para-line/hook，结尾必须留钩子。输出末行 JSON 摘要。" >> daily_run.log 2>&1

rem 3. Run full pipeline (build/verify/audit/deploy)
py -3 daily_originals.py >> daily_run.log 2>&1