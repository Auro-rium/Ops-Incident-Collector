from __future__ import annotations

import signal
import threading


def install_signal_handlers(stop_event: threading.Event) -> None:
    def _stop(_signum, _frame) -> None:
        stop_event.set()

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

