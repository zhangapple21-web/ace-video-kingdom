"""Targeted repair runner: only rejected action probes, reusing per-shot records."""
from pathlib import Path
import subprocess, sys

from tools.probe_contract import write_probe_contract

root = Path(__file__).resolve().parents[1]
manifest = root / "experiments/episode_007_action_probe_tasks_v2.json"
out = root / "media_staging/episode_007_virtual_data/action_probe_v2"
ref = root / "media_staging/episode_007_virtual_data/anchors/user/alang_user_reference.png"
repairs = {
    "P02_PHONE_SLAM_R1": "阿浪穿洗旧浅灰短袖衬衫，接完电话后先短暂停顿蓄力，肩膀和手臂明显加速，把手机重重向下砸在办公桌上；手机接触桌面产生清晰撞击、桌面震动和短暂反弹，手腕随后自然回收，周围同事被冲击惊得抬头。连续完整呈现准备—发力—撞击—惯性回收，真实重量感，快速跟拍，冷峻现实主义竖屏9:16，禁止静态封面和轻放手机。",
    "P05_COPY_PASTE_R1": "深夜密闭办公大厅，阿浪穿浅灰旧短袖衬衫坐在电脑前，连续机械复制、粘贴、鼠标点击、发送；按键和点击节奏有细微不均匀变化，手腕和肩背每次动作后自然回收，屏幕光在脸上变化，镜头持续缓慢拉远，动作在拉远过程中仍继续并留下余波。必须是真实连续动作，不是图片微动或循环表演，冷峻绝望现实主义竖屏9:16。"
}
contract_path = write_probe_contract(
    root / "experiments/episode_007_targeted_repairs_contract.json",
    ({"shot_id": sid, "prompt": prompt, "action": sid} for sid, prompt in repairs.items()),
    episode_id="episode_007_targeted_repairs",
)
for sid, prompt in repairs.items():
    cmd = [sys.executable, str(root/"tools/run_short_clip.py"), "--shot-id", sid,
           "--prompt", prompt, "--episode-contract", str(contract_path), "--admission-scope", "production",
           "--manifest", str(manifest), "--output", str(out/f"{sid}.mp4"),
           "--model", "agnes-video-2.5-flash", "--image", str(ref), "--width", "704", "--height", "1280",
           "--num-frames", "121", "--frame-rate", "24", "--timeout", "600"]
    result = subprocess.run(cmd, cwd=root, check=False)
    if result.returncode:
        raise SystemExit(result.returncode)
