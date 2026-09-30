# -*- coding: utf-8 -*-
from pathlib import Path
import re

def H(s):
    return "".join(chr(int(x, 16)) for x in s.split())

FOLLOW = H("63a8 7406 7ed3 675f 3002 4ece 73b0 5728 8d77 53ea 8f93 51fa 672c 6ce2 573a 6b21 6b63 6587 548c 3010 672c 6ce2 5feb 7167 3011 3002 7b2c 4e00 884c 5fc5 987b 662f ff1a 7b2c 0025 0073 573a 3002 4e0d 8981 601d 8003 8fc7 7a0b ff0c 4e0d 8981 5206 652f ff0c 4e0d 8981 5927 7eb2 3002")
INNER = H("ff08 5185 90e8 63a8 6f14 5df2 5b8c 6210 ff09")
TRUNC = H("4e0a 4e00 6b21 8f93 51fa 88ab 622a 65ad 3002 4ece 65ad 70b9 540e 7ee7 7eed 5199 ff0c 4e0d 8981 91cd 590d 5df2 5199 6bb5 843d ff0c 4e0d 8981 6539 5199 4e8b 5b9e 3002")
CONT = H("8bf7 63a5 7740 5199 5b8c 672c 6ce2 5269 4f59 573a 6b21 548c 3010 672c 6ce2 5feb 7167 3011 3002")

p = Path(r"D:\视频创作\ace-video-kingdom\tools\world_live_evolve.py")
src = p.read_text(encoding="utf-8")
start = src.find("def _call(")
main_at = src.find("def main()")
if start < 0 or main_at < 0:
    raise SystemExit("markers_not_found %s %s" % (start, main_at))

new_fns = '''def _call(messages: list[dict[str, Any]], max_tokens: int, temperature: float, timeout: float) -> dict[str, Any]:
    data, meta = post_chat_completion(
        base_url=_base_url(),
        api_key=_key(),
        model=MODEL,
        messages=messages,
        asset_store=ROOT / "assets" / "cache" / "transport",
        max_tokens=max_tokens,
        temperature=temperature,
        timeout=timeout,
    )
    choice = (data.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    content = str(message.get("content") or "").strip()
    reasoning = str(message.get("reasoning_content") or "").strip()
    finish = str(choice.get("finish_reason") or "")
    actual = str(data.get("model") or MODEL)
    usage = data.get("usage") or {}
    return {
        "content": content,
        "reasoning": reasoning,
        "finish_reason": finish,
        "actual_model": actual,
        "usage": usage,
        "latency_ms": meta.get("latency_ms"),
    }


def _force_wave(prompt: str, start_scene: int) -> dict[str, Any]:
    messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
    result = _call(messages, max_tokens=8192, temperature=0.88, timeout=180.0)
    text = result["content"]
    attempts = [{
        "kind": "primary",
        "finish_reason": result["finish_reason"],
        "content_len": len(text),
        "reasoning_len": len(result["reasoning"]),
        "usage": result["usage"],
        "latency_ms": result["latency_ms"],
    }]
    print("[world-live] primary finish=%s content=%s reasoning=%s usage=%s" % (
        result["finish_reason"], len(text), len(result["reasoning"]), result["usage"]
    ), flush=True)
    if not text:
        follow = FOLLOW % start_scene
        messages = [
            {"role": "user", "content": prompt},
            {
                "role": "assistant",
                "content": result["content"] or INNER,
                "reasoning_content": result["reasoning"],
            },
            {"role": "user", "content": follow},
        ]
        forced = _call(messages, max_tokens=4096, temperature=0.55, timeout=180.0)
        text = forced["content"]
        attempts.append({
            "kind": "force_body",
            "finish_reason": forced["finish_reason"],
            "content_len": len(text),
            "reasoning_len": len(forced["reasoning"]),
            "usage": forced["usage"],
            "latency_ms": forced["latency_ms"],
        })
        print("[world-live] force_body finish=%s content=%s reasoning=%s usage=%s" % (
            forced["finish_reason"], len(text), len(forced["reasoning"]), forced["usage"]
        ), flush=True)
        result = forced
    if text and result["finish_reason"] == "length":
        print("[world-live] truncated, continue", flush=True)
        cont_prompt = CONSTITUTION + "\n" + TRUNC + "\n" + text[-6000:] + "\n" + CONT
        cont = _call([{"role": "user", "content": cont_prompt}], max_tokens=2048, temperature=0.7, timeout=180.0)
        text = text.rstrip() + "\n" + cont["content"]
        attempts.append({
            "kind": "continue",
            "finish_reason": cont["finish_reason"],
            "content_len": len(cont["content"]),
            "reasoning_len": len(cont["reasoning"]),
            "usage": cont["usage"],
            "latency_ms": cont["latency_ms"],
        })
        result = dict(result)
        result["continue"] = attempts[-1]
    if not str(text or "").strip():
        raise RuntimeError(
            "EMPTY_CONTENT finish=%s reasoning_len=%s usage=%s"
            % (result["finish_reason"], len(result.get("reasoning") or ""), result.get("usage"))
        )
    result["content"] = text
    result["attempts"] = attempts
    return result


'''
src = src[:start] + new_fns + src[main_at:]
src2, n = re.subn(
    r"result = _call\(prompt, max_tokens=4096, temperature=0\.88, timeout=180\.0\)[\s\S]*?result\[\"continue\"\] = \{[\s\S]*?\n                \}",
    "result = _force_wave(prompt, next_scene_hint)\n            text = result[\"content\"]",
    src,
    count=1,
)
print("TRY_SUBS", n)
if n != 1:
    raise SystemExit("try_block_not_found")
src = src2
src2, n = re.subn(
    r'("scene_headings": scene_hits,)\n        \}',
    r'\1\n            "attempts": result.get("attempts") or [],\n        }',
    src,
    count=1,
)
print("REC_SUBS", n)
if n != 1:
    raise SystemExit("rec_block_not_found")
src = src2
p.write_text(src, encoding="utf-8")
compile(src, str(p), "exec")
print("PATCHED", p.stat().st_size)
print("HAS_FORCE", "_force_wave" in src)
print("FOLLOW", FOLLOW[:20])