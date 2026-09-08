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

root = Path(
    r"C:\tmp\ace_video_kingdom_git\media_staging\episode_007_virtual_data\anchors"
)
root.mkdir(parents=True, exist_ok=True)
base = os.environ.get(
    "SHENWEN_IMAGE_BASE_URL",
    "https://api.shenwenai.com/v1",
).rstrip("/")
key = os.environ["SHENWEN_IMAGE_API_KEY"]

prompts = [
    (
        "alang_character_anchor.webp",
        "Use case: illustration-story. Asset type: fictional character reference sheet. Primary request: a consistent 24-year-old Chinese male named Alang, gaunt tired face, heavy dark under-eye circles, unwashed short black hair, faded dark hoodie, rubbing his eyes; front, profile, three-quarter views in one coherent sheet, no text, no logos. Style: gritty realistic vertical drama, cold fluorescent office lighting.",
    ),
    (
        "feige_character_anchor.webp",
        "Use case: illustration-story. Asset type: fictional character reference sheet. Primary request: a consistent 35-year-old Chinese male supervisor named Feige, overweight, exhausted anxious eyes, cigarette in hand, wrinkled cheap shirt, smoky cramped office; front, profile, three-quarter views in one coherent sheet, no text, no logos. Style: gritty realistic vertical drama, cold fluorescent office lighting.",
    ),
]

for name, prompt in prompts:
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
            "action": "character_reference_sheet",
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
        raise SystemExit(
            "provider admission blocked: "
            + ";".join(admission["preflight"]["errors"])
        )
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
    assert_admission(
        admission,
        admission["request_hash"],
        provider_payload=payload,
    )
    with urllib.request.urlopen(request, timeout=900) as response:
        result = json.load(response)
    reference = _materialize_image_response(result, root / name)
    print(
        name,
        reference["path"],
        reference["sha256"],
        reference["size_bytes"],
        flush=True,
    )
