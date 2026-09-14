from production_control.privacy_scan import scan_value


def test_privacy_scan_blocks_secrets_without_echoing_raw_value():
    result = scan_value({"prompt": "Authorization: Bearer abcdefghijklmnopqrstuvwxyz123456"})
    assert result["status"] == "BLOCKED_PRIVACY"
    assert result["finding_count"] == 1
    assert "abcdefghijklmnopqrstuvwxyz123456" not in str(result)


def test_privacy_scan_blocks_common_pii():
    result = scan_value({"dialogue": "联系 test@example.com 或 13812345678"})
    assert result["status"] == "BLOCKED_PRIVACY"
    assert {item["kind"] for item in result["findings"]} == {"email", "phone_cn"}


def test_privacy_scan_passes_normal_script_text():
    result = scan_value({"dialogue": "明天准备接粉，先检查设备和合同。"})
    assert result == {
        "schema": "ace.video_kingdom.privacy_scan.v1",
        "status": "PASS",
        "finding_count": 0,
        "findings": [],
    }
