"""Render a local storyboard animatic for Episode 008 (research-only).

This is a reversible placeholder while the external video queue is full. It is
deliberately a graphic animatic, not a claim that provider-generated footage
exists. It uses no private media and no external call.
"""
from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


W, H, FPS = 704, 1280, 12
FONT = r"C:\Windows\Fonts\NotoSansSC-VF.ttf"


def font(size: int):
    return ImageFont.truetype(FONT, size=size)


def fit(draw: ImageDraw.ImageDraw, text: str, max_width: int, fnt):
    words = []
    line = ""
    for ch in text:
        test = line + ch
        if draw.textbbox((0, 0), test, font=fnt)[2] <= max_width:
            line = test
        else:
            words.append(line)
            line = ch
    if line:
        words.append(line)
    return words


def draw_scene(idx: int, t: float) -> Image.Image:
    # subdued blue-black base with a slowly moving warm pool of light
    img = Image.new("RGB", (W, H), (11, 18, 29))
    d = ImageDraw.Draw(img)
    glow = int(26 + 12 * (0.5 + 0.5 * __import__("math").sin(t * 1.3)));
    d.rectangle((0, 0, W, H), fill=(11 + glow // 3, 18 + glow // 4, 29 + glow // 2))
    # room grid
    for y in range(180, 880, 110):
        d.line((40, y, W - 40, y), fill=(29, 48, 65), width=2)
    for x in range(50, W, 110):
        d.line((x, 140, x, 900), fill=(24, 41, 57), width=2)

    title_f = font(30)
    body_f = font(27)
    small_f = font(22)
    d.text((38, 38), "EPISODE 008  /  RESEARCH ANIMATIC", font=small_f, fill=(136, 166, 181))

    if idx == 0:
        d.text((48, 245), "我被卖去东南亚\n居然觉醒了系统", font=font(52), fill=(232, 238, 235), spacing=14)
        d.text((50, 430), "第一眼：系统不替她下结论，\n只把规则的边界照亮。", font=body_f, fill=(120, 213, 201), spacing=10)
        d.rounded_rectangle((48, 640, 656, 830), radius=18, fill=(19, 32, 46), outline=(75, 133, 142), width=3)
        d.text((76, 690), "完全虚构 · 竖屏短剧样片", font=title_f, fill=(225, 207, 157))
        d.text((76, 750), "受骗 → 记录 → 求助 → 依法脱身", font=small_f, fill=(187, 203, 207))
        return img

    # generic office desk and two simplified figures
    d.rectangle((40, 700, 664, 880), fill=(106, 78, 60), outline=(190, 143, 98), width=3)
    d.ellipse((118, 400, 260, 542), fill=(177, 142, 122), outline=(238, 196, 158), width=3)
    d.rectangle((132, 530, 246, 710), fill=(41, 63, 82), outline=(111, 168, 171), width=3)
    d.ellipse((442, 360, 564, 482), fill=(164, 126, 107), outline=(221, 178, 146), width=3)
    d.rectangle((446, 470, 560, 700), fill=(85, 85, 81), outline=(164, 159, 136), width=3)

    # paper/phone objects
    if idx == 1:
        d.rounded_rectangle((280, 560, 584, 755), radius=8, fill=(236, 226, 202), outline=(247, 240, 218), width=3)
        d.text((302, 592), "离开条件：", font=body_f, fill=(42, 48, 53))
        d.line((302, 652, 540, 652), fill=(108, 117, 121), width=3)
        d.text((300, 675), "（空白）", font=small_f, fill=(179, 75, 65))
        d.text((92, 230), "可见字段：离开条件｜空白", font=title_f, fill=(111, 224, 205))
        d.text((92, 270), "动作：写下“请补充具体条件”", font=small_f, fill=(215, 220, 211))
        d.text((92, 950), "陈岳：签字，完成量到了，就能离开。", font=small_f, fill=(223, 230, 226))
        d.text((92, 1000), "林岚：合同里没有写离开条件。", font=small_f, fill=(120, 213, 201))
    elif idx == 2:
        for j, label in enumerate(("班次表", "扣费单", "个人记录")):
            x = 90 + j * 185
            d.rounded_rectangle((x, 520, x + 150, 735), radius=8, fill=(236, 226, 202), outline=(247, 240, 218), width=3)
            d.text((x + 18, 560), label, font=small_f, fill=(42, 48, 53))
            d.line((x + 18, 620, x + 128, 620), fill=(127, 137, 140), width=3)
            d.line((x + 18, 665, x + 128, 665), fill=(127, 137, 140), width=3)
        d.text((84, 230), "系统：金额不一致｜待核验", font=title_f, fill=(111, 224, 205))
        d.text((84, 270), "席位：招聘端 / 审批端 / 执行端", font=small_f, fill=(215, 220, 211))
        d.text((92, 950), "阿棠：同一天，这张扣费单和我的记录对不上。", font=small_f, fill=(120, 213, 201))
        d.text((92, 1000), "林岚：把承诺、实际、收款，逐项对齐。", font=small_f, fill=(223, 230, 226))
    else:
        d.rounded_rectangle((210, 500, 500, 760), radius=22, fill=(24, 41, 54), outline=(111, 224, 205), width=4)
        d.text((246, 545), "安澜公共求助中心", font=small_f, fill=(221, 230, 225))
        d.text((246, 620), "已接通", font=font(42), fill=(111, 224, 205))
        d.text((246, 690), "案件编号：AL-0472", font=small_f, fill=(225, 207, 157))
        d.text((88, 230), "可验证结果：时间线 / 单据 / 签字状态", font=title_f, fill=(111, 224, 205))
        d.text((88, 270), "下一步：依法核验，不靠个人对抗", font=small_f, fill=(215, 220, 211))
        d.text((92, 950), "阿棠：现在联系公共求助中心，按流程来。", font=small_f, fill=(120, 213, 201))
        d.text((92, 1000), "林岚：我不是靠奇迹逃走，是让证据推动规则生效。", font=small_f, fill=(223, 230, 226))

    # system rail stays above the subtitle safe zone
    rail = [("席位", (120, 213, 201)), ("获利", (225, 207, 157)), ("代价", (214, 135, 119)), ("可验证规则", (182, 198, 211))]
    x0 = 72
    for label, color in rail:
        d.rounded_rectangle((x0, 1080, x0 + 130, 1128), radius=9, fill=(20, 31, 43), outline=color, width=2)
        d.text((x0 + 12, 1090), label, font=small_f, fill=color)
        x0 += 148
    d.text((50, 1188), "故事与地点均为虚构｜研究样片，非现实案件陈述", font=small_f, fill=(142, 160, 170))
    return img


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--srt", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.srt.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="episode008_animatic_") as tmp:
        frames = Path(tmp)
        total = 15 * FPS
        for n in range(total):
            t = n / FPS
            idx = 0 if t < 2.5 else (1 if t < 6.5 else (2 if t < 10.5 else 3))
            local_t = t if idx == 0 else t - (2.5 if idx == 1 else 6.5 if idx == 2 else 10.5)
            frame = draw_scene(idx, local_t)
            frame.save(frames / f"f{n:04d}.png")
        encoded = subprocess.run([
            "ffmpeg", "-y", "-framerate", str(FPS), "-i", str(frames / "f%04d.png"),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(args.output),
        ], check=False, capture_output=True, text=True)
        if encoded.returncode:
            raise RuntimeError(encoded.stderr[-2000:])
    args.srt.write_text(
        "1\n00:00:00,000 --> 00:00:02,400\n第一眼：系统不替她下结论，只把规则的边界照亮。\n\n"
        "2\n00:00:02,500 --> 00:00:06,400\n陈岳：签字，完成量到了，就能离开。\n林岚：合同里没有写离开条件。\n\n"
        "3\n00:00:06,500 --> 00:00:10,400\n阿棠：同一天，这张扣费单和我的记录对不上。\n林岚：把承诺、实际、收款，逐项对齐。\n\n"
        "4\n00:00:10,500 --> 00:00:15,000\n阿棠：现在联系公共求助中心，按流程来。\n林岚：让证据推动规则生效。\n",
        encoding="utf-8",
    )
    print(f"{{\"status\":\"ANIMATIC_RENDERED\",\"output\":\"{args.output}\",\"duration_seconds\":15,\"fps\":{FPS}}}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
