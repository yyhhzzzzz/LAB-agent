import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any, Optional


_PASSWORD_SCHEME = "pbkdf2_sha256"
_PASSWORD_ITERATIONS = 600_000
_MAX_PASSWORD_ITERATIONS = 2_000_000
_TOKEN_HEADER = {"alg": "HS256", "typ": "JWT"}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _PASSWORD_ITERATIONS
    )
    return "{}${}${}${}".format(
        _PASSWORD_SCHEME,
        _PASSWORD_ITERATIONS,
        _b64encode(salt),
        _b64encode(digest),
    )


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        scheme, iterations_value, encoded_salt, encoded_digest = encoded_hash.split("$")
        iterations = int(iterations_value)
        salt = _b64decode(encoded_salt)
        expected_digest = _b64decode(encoded_digest)
        if (
            scheme != _PASSWORD_SCHEME
            or iterations < 1
            or iterations > _MAX_PASSWORD_ITERATIONS
            or len(salt) < 16
            or len(expected_digest) != hashlib.sha256().digest_size
        ):
            return False
        actual_digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, iterations
        )
        return hmac.compare_digest(actual_digest, expected_digest)
    except (AttributeError, TypeError, ValueError):
        return False


def create_access_token(
    subject: str, secret: str, expires_in_minutes: int, now: Optional[int] = None
) -> str:
    issued_at = int(time.time()) if now is None else now
    payload = {"sub": subject, "iat": issued_at, "exp": issued_at + expires_in_minutes * 60}
    encoded_header = _encode_json(_TOKEN_HEADER)
    encoded_payload = _encode_json(payload)
    signing_input = "{}.{}".format(encoded_header, encoded_payload).encode("ascii")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return "{}.{}.{}".format(encoded_header, encoded_payload, _b64encode(signature))


def decode_access_token(token: str, secret: str, now: Optional[int] = None) -> Optional[str]:
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
        signing_input = "{}.{}".format(encoded_header, encoded_payload).encode("ascii")
        expected_signature = hmac.new(
            secret.encode("utf-8"), signing_input, hashlib.sha256
        ).digest()
        if not hmac.compare_digest(expected_signature, _b64decode(encoded_signature)):
            return None
        header = json.loads(_b64decode(encoded_header))
        payload: Any = json.loads(_b64decode(encoded_payload))
        current_time = int(time.time()) if now is None else now
        if (
            header != _TOKEN_HEADER
            or not isinstance(payload, dict)
            or not isinstance(payload.get("sub"), str)
            or not payload["sub"]
            or not isinstance(payload.get("exp"), int)
            or payload["exp"] <= current_time
        ):
            return None
        return payload["sub"]
    except (AttributeError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _encode_json(value: dict) -> str:
    return _b64encode(json.dumps(value, separators=(",", ":")).encode("utf-8"))


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
