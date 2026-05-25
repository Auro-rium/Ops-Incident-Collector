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


def test_classifier_detects_go_as_code() -> None:
    detected = classify_content(
        Path("service/history/handler.go"),
        ".go",
        relative_path="service/history/handler.go",
        text="package history\nfunc StartWorkflowTask() {}\n",
    )

    assert detected == "code"


def test_classifier_detects_proto_as_api_doc() -> None:
    detected = classify_content(
        Path("proto/temporal/server/api/historyservice/v1/service.proto"),
        ".proto",
        relative_path="proto/temporal/server/api/historyservice/v1/service.proto",
        text='syntax = "proto3";\nservice HistoryService {}\n',
    )

    assert detected == "api_doc"


def test_classifier_detects_typescript_as_code() -> None:
    detected = classify_content(
        Path("src/history/service.ts"),
        ".ts",
        relative_path="src/history/service.ts",
        text="export async function startWorkflowTask() {}",
    )

    assert detected == "code"
