from __future__ import annotations

from pathlib import Path
from typing import Iterable

from opsincident_collector.core.models import SourceItem


class BaseReceiver:
    def discover(self, path: Path) -> Iterable[SourceItem]:
        raise NotImplementedError
