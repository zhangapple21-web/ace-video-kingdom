from urllib.parse import parse_qs, urlparse

import pytest

from runtime.filebase_presign import MAX_EXPIRES, presign_get_url


def test_filebase_presign_is_https_and_caps_expiry():
    url = presign_get_url(
        endpoint="https://s3.filebase.io",
        bucket="bucket",
        key="anchors/角色.png",
        access_key="AKIA_TEST",
        secret_key="SECRET_TEST",
        expires=MAX_EXPIRES + 1,
    )
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    assert parsed.scheme == "https"
    assert parsed.netloc == "s3.filebase.io"
    assert query["X-Amz-Expires"] == [str(MAX_EXPIRES)]
    assert len(query["X-Amz-Signature"][0]) == 64
    assert parsed.path.startswith("/bucket/anchors/")


def test_filebase_presign_rejects_non_https_endpoint():
    with pytest.raises(ValueError, match="HTTPS"):
        presign_get_url(
            endpoint="http://s3.filebase.io",
            bucket="bucket",
            key="anchor.png",
            access_key="AKIA_TEST",
            secret_key="SECRET_TEST",
        )
