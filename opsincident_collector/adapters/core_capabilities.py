from __future__ import annotations

from opsincident_collector.adapters.core_contracts import CoreCapabilities


def supports_feature(capabilities: CoreCapabilities | None, feature: str) -> bool:
    return bool(capabilities and capabilities.features.get(feature))
