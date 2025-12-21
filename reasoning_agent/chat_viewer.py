from __future__ import annotations

import sys
import time
from pathlib import Path


def tail_file(path: Path) -> None:
    """
    Simple tail-like loop to stream new lines to stdout.
    """
    print(f"[chat-viewer] Watching log: {path}", flush=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(exist_ok=True)

    with path.open("r", encoding="utf-8") as log_file:
        # Start from current position to show existing content as well.
        while True:
            line = log_file.readline()
            if line:
                print(line.rstrip("\n"), flush=True)
            else:
                time.sleep(0.2)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: chat_viewer.py <path_to_log>", flush=True)
        return
    tail_file(Path(sys.argv[1]).expanduser())


if __name__ == "__main__":
    main()


