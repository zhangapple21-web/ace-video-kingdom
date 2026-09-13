from pathlib import Path
import subprocess, sys

from tools.probe_contract import write_probe_contract
root = Path(__file__).resolve().parents[1]
out=root/"media_staging/episode_007_virtual_data/camera_probe_v2"; out.mkdir(parents=True,exist_ok=True)
manifest=root/"experiments/episode_007_camera_probe_v2_tasks.json"
a=root/"media_staging/episode_007_virtual_data/anchors/scene_action"
shots=[
("C01_DIALOGUE_LOCKED","office_keyboard.png","阿浪穿浅灰旧短袖衬衫，在拥挤办公室里完整说完一句压抑台词。镜头 locked-off 中近景，整段不横移、不环绕、不快速推拉，只允许人物嘴部、眼神和手部自然表演；表演完成后再停留一拍。动作从场景中段开始，禁止静态肖像开头。"),
("C02_PHONE_SINGLE_JOLT","office_phone_impact.png","阿浪穿浅灰旧短袖衬衫，先蓄力再把手机重重砸桌。镜头全程固定，只有手机接触桌面的瞬间产生一次短促机位震动，随后立即恢复固定并展示手机反弹和手腕回收；不得横移、环绕或连续变焦。"),
("C03_DESK_SINGLE_PUSH","manager_desk_impact.png","肥哥穿黑色短袖POLO，完整吼完一句话。镜头先固定中景，拍桌发力瞬间只做一次极短微推和轻微震动，动作结束后固定停留展示烟雾、纸张和表情回收；不得持续移动。"),
("C04_DIALOGUE_PULLBACK_LATE","night_copy_pullback.png","阿浪穿浅灰旧短袖衬衫先在固定机位完成连续复制粘贴和发送动作，保持动作和节奏清晰；只有动作稳定建立并接近镜头结尾时，才进行一次缓慢向后拉远，拉远后不再切镜，人物动作继续。")]
contract_path = write_probe_contract(
    root / "experiments/episode_007_camera_probe_v2_contract.json",
    ({"shot_id": sid, "prompt": prompt, "action": sid} for sid, _anchor, prompt in shots),
    episode_id="episode_007_camera_probe_v2",
)
for sid,anchor,prompt in shots:
 cmd=[sys.executable,str(root/"tools/run_short_clip.py"),"--shot-id",sid,"--prompt",prompt,"--episode-contract",str(contract_path),"--admission-scope","production","--manifest",str(manifest),"--output",str(out/f"{sid}.mp4"),"--model","agnes-video-2.5-flash","--image",str(a/anchor),"--width","704","--height","1280","--num-frames","241","--frame-rate","24","--timeout","900"]
 result = subprocess.run(cmd,cwd=root,check=False)
 if result.returncode:
  raise SystemExit(result.returncode)
