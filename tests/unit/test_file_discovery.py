from pathlib import Path

from opsincident_collector.receivers.filesystem import discover_files


def test_discover_files_respects_depth_and_globs(tmp_path: Path) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "b").mkdir()
    (tmp_path / "a" / "one.md").write_text("hello", encoding="utf-8")
    (tmp_path / "a" / "b" / "two.py").write_text("print('x')", encoding="utf-8")

    items = list(discover_files(tmp_path, max_depth=2, include=["**/*.md", "**/*.py"]))

    assert sorted(item.relative_path for item in items) == ["a/b/two.py", "a/one.md"]
