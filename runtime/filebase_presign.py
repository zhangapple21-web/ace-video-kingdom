from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime, timezone
from urllib.parse import quote


MAX_EXPIRES = 604800


def _hmac(key: bytes, value: str) -> bytes:
    return hmac.new(key, value.encode("utf-8"), hashlib.sha256).digest()


def presign_get_url(*, endpoint: str, bucket: str, key: str, access_key: str, secret_key: str, region: str = "us-east-1", expires: int = MAX_EXPIRES) -> str:
    """Create an S3 SigV4 GET URL without persisting credentials or the URL."""
    expires = max(1, min(int(expires), MAX_EXPIRES))
    endpoint = endpoint.rstrip("/")
    parsed = endpoint.split("://", 1)
    if len(parsed) != 2 or not parsed[1]:
        raise ValueError("FILEBASE_ENDPOINT must be an absolute HTTPS URL")
    scheme, authority = parsed
    if scheme.lower() != "https":
        raise ValueError("FILEBASE_ENDPOINT must use HTTPS")
    host = authority.split("/", 1)[0]
    encoded_key = quote(key.lstrip("/"), safe="/-_.~")
    canonical_uri = f"/{quote(bucket, safe='-_.~')}/{encoded_key}"
    now = datetime.now(timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")
    credential_scope = f"{date_stamp}/{region}/s3/aws4_request"
    query = {
        "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
        "X-Amz-Credential": f"{access_key}/{credential_scope}",
        "X-Amz-Date": amz_date,
        "X-Amz-Expires": str(expires),
        "X-Amz-SignedHeaders": "host",
    }
    canonical_query = "&".join(
        f"{quote(k, safe='-_.~')}={quote(v, safe='-_.~')}" for k, v in sorted(query.items())
    )
    canonical_headers = f"host:{host}\n"
    canonical_request = "\n".join(("GET", canonical_uri, canonical_query, canonical_headers, "host", "UNSIGNED-PAYLOAD"))
    string_to_sign = "\n".join(("AWS4-HMAC-SHA256", amz_date, credential_scope, hashlib.sha256(canonical_request.encode()).hexdigest()))
    k_date = _hmac(("AWS4" + secret_key).encode("utf-8"), date_stamp)
    k_region = hmac.new(k_date, region.encode(), hashlib.sha256).digest()
    k_service = hmac.new(k_region, b"s3", hashlib.sha256).digest()
    k_signing = hmac.new(k_service, b"aws4_request", hashlib.sha256).digest()
    query["X-Amz-Signature"] = hmac.new(k_signing, string_to_sign.encode(), hashlib.sha256).hexdigest()
    final_query = "&".join(f"{quote(k, safe='-_.~')}={quote(v, safe='-_.~')}" for k, v in sorted(query.items()))
    return f"{scheme}://{host}{canonical_uri}?{final_query}"


def presign_from_env(key: str) -> str:
    access_key = os.environ.get("FILEBASE_ACCESS_KEY", "").strip()
    secret_key = os.environ.get("FILEBASE_SECRET_KEY", "").strip()
    if not access_key or not secret_key:
        raise RuntimeError("FILEBASE_ACCESS_KEY/FILEBASE_SECRET_KEY 未配置，无法自动生成 7 天 URL")
    return presign_get_url(
        endpoint=os.environ.get("FILEBASE_ENDPOINT", "https://s3.filebase.io"),
        bucket=os.environ.get("FILEBASE_BUCKET", "r22021111"),
        key=key,
        access_key=access_key,
        secret_key=secret_key,
        region=os.environ.get("FILEBASE_REGION", "us-east-1"),
        expires=int(os.environ.get("FILEBASE_URL_TTL_SECONDS", str(MAX_EXPIRES))),
    )
