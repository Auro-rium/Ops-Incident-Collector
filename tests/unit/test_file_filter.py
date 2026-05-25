from pathlib import Path

from opsincident_collector.processors.file_filter import (
    detect_possible_secret_count,
    is_binary_file,
    is_supported_extension,
)
from opsincident_collector.processors.path_policy import is_denied_path


def test_supported_extension_detection() -> None:
    assert is_supported_extension(".md") is True
    assert is_supported_extension(".go") is True
    assert is_supported_extension(".proto") is True
    assert is_supported_extension(".pdf") is False


def test_denied_path_detection() -> None:
    assert is_denied_path(".env", [".env", "*.pem"]) is True
    assert is_denied_path("src/app.py", [".env", "*.pem"]) is False


def test_binary_and_secret_detection(tmp_path: Path) -> None:
    binary_path = tmp_path / "blob.bin"
    binary_path.write_bytes(b"\x00\x01\x02")
    assert is_binary_file(binary_path) is True

    secret_path = tmp_path / "app.log"
    secret_path.write_text("Bearer abc123\npassword=supersecret", encoding="utf-8")
    assert detect_possible_secret_count(secret_path) >= 2
