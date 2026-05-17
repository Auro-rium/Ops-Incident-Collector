from pathlib import Path

from opsincident_collector.processors.content_classifier import classify_content


def test_classifier_prefers_relative_path_over_misleading_absolute_path(tmp_path: Path) -> None:
    misleading_root = tmp_path / "incident-root"
    path = misleading_root / "src" / "service.py"
    path.parent.mkdir(parents=True)
    path.write_text("def handle_order():\n    return True\n", encoding="utf-8")

    detected = classify_content(
        path,
        ".py",
        relative_path="src/service.py",
        text=path.read_text(encoding="utf-8"),
    )

    assert detected == "code"
