import json
import os
import sys
import urllib.request
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from runtime.provider_admission import (
    admit_provider_request,
    assert_admission,
    build_canonical_generation_request,
)
from tools.run_idea_pipeline import _materialize_image_response

root = repo_root / "media_staging" / "episode_007_virtual_data" / "anchors" / "scene_action"
root.mkdir(parents=True, exist_ok=True)
base = os.environ.get(
    "SHENWEN_IMAGE_BASE_URL",
    "https://api.shenwenai.com/v1",
).rstrip("/")
key = os.environ["SHENWEN_IMAGE_API_KEY"]
prompts = {
    "office_keyboard": "竖屏9:16电影剧照，东南亚密闭廉价写字楼开放式办公室，阿浪是24岁瘦削中国男性，重黑眼圈，洗旧浅灰短袖衬衫，双手正在猛烈连续敲击键盘，桌面有电脑、手机和文件，手部处于动作中段而非摆拍肖像，冷白荧光灯与绿色屏幕光，现实主义压抑风格，不要连帽衫，不要静态角色海报。",
    "office_phone_impact": "竖屏9:16电影剧照，拥挤办公室桌面，阿浪穿洗旧浅灰短袖衬衫，手臂正在把手机重重砸向桌面，手机接触桌面、纸张被震起、同事惊讶抬头，动作冲击瞬间，冷峻现实主义，重黑眼圈，不要连帽衫，不要静态肖像。",
    "manager_desk_impact": "竖屏9:16电影剧照，狭小烟雾弥漫主管办公室，肥哥35岁偏胖中国男性穿黑色短袖POLO，手掌正在猛拍堆满报表的桌面，烟灰缸和纸张震动，烟雾在廉价灯光中可见，动作冲击瞬间，冷峻现实主义，不要夸张卡通。",
    "night_copy_pullback": "竖屏9:16电影剧照，深夜密闭办公大厅只剩电脑蓝光，阿浪穿洗旧浅灰短袖衬衫坐在工位，双手一边键盘复制粘贴一边鼠标点击发送，桌面电脑和文件清晰可见，镜头正在向后拉远，动作进行中，绝望冷峻现实主义，不要连帽衫，不要静态海报。",
}

for name, prompt in prompts.items():
    target = root / f"{name}.webp"
    if target.is_file():
        print(name, "EXISTS", flush=True)
        continue
    payload = {
        "model": "gpt-image-2",
        "prompt": prompt,
        "size": "1024x1536",
        "quality": "medium",
        "n": 1,
    }
    canonical = build_canonical_generation_request(
        {
            "episode_id": "episode_007",
            "shot_id": f"ASSET_{name}",
            "prompt": prompt,
            "action": "scene_action_anchor",
            "camera": {"framing": "asset_reference_sheet", "movement": "NONE"},
            "visible_entities": [name],
            "audio_contract": {"status": "NOT_APPLICABLE"},
            "reference_assets": [],
        },
        payload,
        provider="shenwen-image",
        endpoint=f"{base}/images/generations",
        payload_schema="openai.images.generations.v1",
        model="gpt-image-2",
        scope="research",
        request_kind="asset",
    )
    admission = admit_provider_request(
        canonical,
        receipt_path=repo_root / "research" / "admission_receipts" / f"episode_007_{name}.json",
    )
    if admission["status"] != "ADMITTED":
        raise SystemExit("provider admission blocked: " + ";".join(admission["preflight"]["errors"]))
    request = urllib.request.Request(
        f"{base}/images/generations",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Idempotency-Key": f"vk-{admission['request_hash']}",
        },
        method="POST",
    )
    assert_admission(admission, admission["request_hash"], provider_payload=payload)
    with urllib.request.urlopen(request, timeout=900) as response:
        result = json.load(response)
    reference = _materialize_image_response(result, target)
    print(name, reference["path"], reference["sha256"], reference["size_bytes"], flush=True)
