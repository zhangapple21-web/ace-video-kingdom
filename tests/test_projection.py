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


def test_projection_orders_timestamped_prefix_before_dynamic_tail():
    messages = [
        {"text": "时间30", "timestamp": 30},
        {"text": "时间10", "timestamp": 10},
        {"text": "时间40", "timestamp": 40},
        {"text": "时间20", "timestamp": 20},
    ]
    result = project_messages(messages, stable_head=2, dynamic_tail=2)

    assert [item["text"] for item in result["messages"]] == ["时间10", "时间20", "时间30", "时间40"]

    protected = project_messages(
        [{"text": "结论：保留", "timestamp": 15}, *messages],
        stable_head=1,
        dynamic_tail=1,
    )
    assert [item["text"] for item in protected["messages"]] == ["时间10", "结论：保留", "时间40"]


def test_projection_parses_iso_time_and_falls_back_to_input_order_for_untimed_messages():
    messages = [
        {"text": "较晚 ISO", "timestamp": "2025-01-02T00:00:00Z"},
        {"text": "无时间一"},
        {"text": "较早 ISO", "created_at": "2025-01-01T00:00:00+00:00"},
        {"text": "无时间二"},
    ]
    result = project_messages(messages, stable_head=4, dynamic_tail=0)

    assert [item["text"] for item in result["messages"]] == ["较早 ISO", "较晚 ISO", "无时间一", "无时间二"]

    tail_only = project_messages(messages, stable_head=0, dynamic_tail=2)
    assert [item["text"] for item in tail_only["messages"]] == ["无时间一", "无时间二"]
