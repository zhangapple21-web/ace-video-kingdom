from pathlib import Path
import subprocess, sys

from tools.probe_contract import write_probe_contract

root=Path(__file__).resolve().parents[1]
manifest=root/"experiments/episode_007_scene_anchor_probe_tasks.json"
out=root/"media_staging/episode_007_virtual_data/scene_anchor_probe"
out.mkdir(parents=True,exist_ok=True)
shots=[
 ("A01_KEYBOARD_SCENE","office_keyboard.png","阿浪保持同一张憔悴面孔、重黑眼圈和浅灰旧短袖衬衫；从已经在键盘上方的手开始，连续快速敲击，揉眼后立即继续敲击，镜头近距离跟随手和眼睛，必须从动作中开始，不要静态肖像。"),
 ("A02_PHONE_IMPACT_SCENE","office_phone_impact.png","阿浪保持同一张憔悴面孔、重黑眼圈和浅灰旧短袖衬衫；手臂先蓄力再快速把手机重重砸向桌面，桌面和纸张震动，手机短暂反弹，手腕回收，镜头跟随撞击，必须从动作中开始。"),
 ("A03_DESK_IMPACT_SCENE","manager_desk_impact.png","肥哥保持同一张偏胖面孔、黑色短袖POLO和香烟；身体前倾用力拍桌，报表和烟灰缸产生冲击反馈，烟雾移动，镜头随撞击轻微震动，必须从动作中开始。"),
 ("A04_NIGHT_COPY_SCENE","night_copy_pullback.png","阿浪保持同一张憔悴面孔、重黑眼圈和浅灰旧短袖衬衫；已经在连续复制、粘贴、点击发送，动作节奏略不均匀，肩背自然回收，镜头持续向后拉远，动作不能停。")]
contract_path = write_probe_contract(
    root / "experiments/episode_007_scene_anchor_probe_contract.json",
    ({"shot_id": sid, "prompt": prompt, "action": sid} for sid, _anchor, prompt in shots),
    episode_id="episode_007_scene_anchor_probe",
)
for sid,anchor,prompt in shots:
 cmd=[sys.executable,str(root/"tools/run_short_clip.py"),"--shot-id",sid,"--prompt",prompt,"--episode-contract",str(contract_path),"--admission-scope","production","--manifest",str(manifest),"--output",str(out/f"{sid}.mp4"),"--model","agnes-video-2.5-flash","--width","704","--height","1280","--seconds","5","--aspect-ratio","9:16","--flash-mode","text","--timeout","900"]
 result = subprocess.run(cmd,cwd=root,check=False)
 if result.returncode:
  raise SystemExit(result.returncode)
