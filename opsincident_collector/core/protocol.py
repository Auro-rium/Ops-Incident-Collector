from __future__ import annotations

from importlib import metadata

SCHEMA_VERSION = "incidentops.normalized_document.v1"
CORE_API_VERSION = "v1"
DEFAULT_COLLECTOR_VERSION = "0.1.0"


def collector_version() -> str:
    try:
        return metadata.version("opsincident-collector")
    except metadata.PackageNotFoundError:
        try:
            from opsincident_collector import __version__

            return __version__
        except Exception:
            return DEFAULT_COLLECTOR_VERSION
