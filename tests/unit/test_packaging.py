from pathlib import Path


def test_pyproject_does_not_ship_collector_mcp_extra() -> None:
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")

    assert "mcp = [" not in pyproject
    assert "mcp>=" not in pyproject


def test_dockerfile_supports_install_target_build_arg() -> None:
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")

    assert 'ARG INSTALL_TARGET="."' in dockerfile
    assert 'pip install --no-cache-dir "${INSTALL_TARGET}"' in dockerfile
