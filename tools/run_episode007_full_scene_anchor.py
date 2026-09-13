from pathlib import Path
import subprocess, sys

from tools.probe_contract import write_probe_contract
root = Path(__file__).resolve().parents[1]
out=root/"media_staging/episode_007_virtual_data/full_scene_anchor"
out.mkdir(parents=True,exist_ok=True)
manifest=root/"experiments/episode_007_full_scene_anchor_tasks.json"
anchors=root/"media_staging/episode_007_virtual_data/anchors/scene_action"
shots=[
("F01","office_keyboard.png","阿浪穿浅灰旧短袖衬衫，拥挤办公室里连续猛烈敲键盘，揉眼后立刻继续，镜头从手部推到疲惫眼睛，动作从进行中开始。"),
("F02","office_keyboard.png","阿浪穿浅灰旧短袖衬衫同时操作多个工作窗口，手指快速复制粘贴，手机不断震动，镜头横移跟随，动作持续。"),
("F03","office_phone_impact.png","阿浪穿浅灰旧短袖衬衫接完电话，蓄力后把手机重重砸向桌面，纸张震动，手机反弹，手腕回收，镜头跟拍撞击。"),
("F04","manager_desk_impact.png","肥哥穿黑色短袖POLO，夹烟猛拍报表桌面，烟灰和纸张被震起，身体前倾吼叫，镜头随冲击抖动。"),
("F05","manager_desk_impact.png","阿浪穿浅灰旧短袖衬衫站在肥哥桌前质问工资，肥哥吐烟、转身指向屏幕，双方保持压抑对峙，镜头缓慢环绕。"),
("F06","office_keyboard.png","开放式大厅里男同事站起又坐下，阿浪握拳，所有人继续敲键盘，镜头从拳头拉到群像，情绪压迫。"),
("F07","office_phone_impact.png","阿浪穿浅灰旧短袖衬衫盯着手机新好友申请，眼神短暂亮起，猛地起身抓起手机，镜头快速推近。"),
("F08","office_keyboard.png","阿浪穿浅灰旧短袖衬衫对着电脑温柔打字，屏幕光映脸，手指点击发送后停顿，镜头近距离推进。"),
("F09","office_phone_impact.png","手机显示到账提示，阿浪猛地站起向同事喊叫，周围人围拢，随后红色警告光映在所有人脸上，镜头快速移动。"),
("F10","manager_desk_impact.png","肥哥穿黑色短袖POLO接老板电话，机械抽烟，挂断后肩膀垮下，阿浪出现在门口，镜头从烟灰缸移到两人。"),
("F11","night_copy_pullback.png","深夜大厅只剩电脑蓝光，阿浪穿浅灰旧短袖衬衫机械复制粘贴发送，镜头持续拉远到空旷办公室，动作不停，绝望麻木。")]
contract_path = write_probe_contract(
    root / "experiments/episode_007_full_scene_anchor_contract.json",
    ({"shot_id": sid, "prompt": prompt, "action": sid} for sid, _anchor, prompt in shots),
    episode_id="episode_007_full_scene_anchor",
)
for sid,anchor,prompt in shots:
 cmd=[sys.executable,str(root/"tools/run_short_clip.py"),"--shot-id",sid,"--prompt",prompt,"--episode-contract",str(contract_path),"--admission-scope","production","--manifest",str(manifest),"--output",str(out/f"{sid}.mp4"),"--model","agnes-video-2.5-flash","--image",str(anchors/anchor),"--width","704","--height","1280","--num-frames","241","--frame-rate","24","--timeout","900"]
 result = subprocess.run(cmd,cwd=root,check=False)
 if result.returncode:
  raise SystemExit(result.returncode)
