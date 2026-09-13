import base64
import io

from PIL import Image

from production_control.projection import project_messages


def _png_bytes(size=(1800, 1200)):
    image = Image.new("RGB", size, (30, 90, 160))
    out = io.BytesIO()
    image.save(out, format="PNG")
    return base64.b64encode(out.getvalue()).decode("ascii")


def test_projection_enforces_per_image_and_aggregate_caps():
    encoded = _png_bytes()
    messages = [
        {"role": "user", "text": "参考图", "image": encoded},
        {"role": "assistant", "text": "重复旁白", "image": encoded},
        {"role": "assistant", "text": "结论：角色包已锁定；下一步：生成第1镜"},
    ]
    result = project_messages(messages, image_cap=64 * 1024, aggregate_cap=100 * 1024)
    assert result["within_budget"] is True
    assert result["image_bytes"] <= 100 * 1024
    assert result["protected_conclusions"] == 1
    assert any("结论" in str(item.get("text")) for item in result["messages"])


def test_projection_is_deterministic_for_same_input():
    messages = [{"role": "assistant", "text": "结论：保留"}, {"role": "user", "text": "噪声"}]
    first = project_messages(messages)
    second = project_messages(messages)
    assert first == second


def test_projection_defers_protected_visual_instead_of_exceeding_aggregate_cap():
    messages = [{
        "role": "assistant",
        "text": "结论：角色包已锁定",
        "image": _png_bytes((2400, 1600)),
    }]
    result = project_messages(messages, image_cap=512 * 1024, aggregate_cap=8 * 1024)
    assert result["within_budget"] is True
    assert result["projection_blocked"] is False
    assert result["visuals_deferred"] is True
    assert result["messages"][0]["image"]["asset_ref"].startswith("sha256:")
