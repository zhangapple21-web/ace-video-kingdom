"""Action-first probe renders for episode 007."""
from pathlib import Path
import subprocess, sys

from tools.probe_contract import write_probe_contract

root=Path(__file__).resolve().parents[1]
manifest=root/"experiments/episode_007_action_probe_tasks_v2.json"
out=root/"media_staging/episode_007_virtual_data/action_probe_v2"
out.mkdir(parents=True,exist_ok=True)
shots=[
("P01_KEYBOARD","阿浪穿洗旧浅灰短袖衬衫坐在拥挤办公室工位，手指快速连续敲击键盘，镜头从手部特写快速推到布满血丝的眼睛，他揉眼后继续猛敲，动作必须连续可见，冷峻现实主义，竖屏9:16，不要静态肖像，不要连帽卫衣","alang_character_anchor.png"),
("P02_PHONE_SLAM","阿浪穿洗旧浅灰短袖衬衫接完电话，愤怒地抬手把手机重重砸在办公桌上，手机弹起，周围同事同时抬头又低下，镜头快速摇移跟随撞击，动作幅度大，冷峻现实主义，竖屏9:16，不要静态封面","alang_character_anchor.png"),
("P03_DESK_SLAM","肥哥穿黑色短袖Polo在狭小主管办公室里暴躁猛拍桌面，报表和烟灰缸震动，烟灰飞起，他身体前倾吼叫，镜头随桌面冲击抖动，动作必须清楚，冷峻现实主义，竖屏9:16","feige_character_anchor.png"),
("P04_RUN_OUT","阿浪穿洗旧浅灰短袖衬衫从工位猛地站起，推开椅子，穿过拥挤办公桌向前跑，手里攥着手机，镜头手持跟拍，背景同事转头，必须有明显位移，冷峻现实主义，竖屏9:16","alang_character_anchor.png"),
("P05_COPY_PASTE","深夜办公大厅只剩零星灯光，阿浪穿浅灰旧衬衫疲惫坐在电脑前，手指机械地复制、粘贴、发送，镜头从键盘缓慢拉远到整间死寂办公室，屏幕光变化，动作持续，冷峻绝望现实主义，竖屏9:16","alang_character_anchor.png"),
]
contract_path = write_probe_contract(
    root / "experiments/episode_007_action_probe_contract.json",
    ({"shot_id": sid, "prompt": prompt, "action": sid} for sid, prompt, _anchor in shots),
    episode_id="episode_007_action_probe",
)
for sid,prompt,anchor in shots:
    official = "feige_user_reference.png" if sid == "P03_DESK_SLAM" else "alang_user_reference.png"
    cmd=[sys.executable,str(root/"tools/run_short_clip.py"),"--shot-id",sid,"--prompt",prompt,"--episode-contract",str(contract_path),"--admission-scope","production","--manifest",str(manifest),"--output",str(out/f"{sid}.mp4"),"--model","agnes-video-2.5-flash","--image",str(root/"media_staging/episode_007_virtual_data/anchors/user"/official),"--width","704","--height","1280","--num-frames","121","--frame-rate","24","--timeout","600"]
    result = subprocess.run(cmd,cwd=root,check=False)
    if result.returncode:
        raise SystemExit(result.returncode)
