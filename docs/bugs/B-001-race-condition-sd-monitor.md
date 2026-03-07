# B-001: Race condition in sd_monitor process management

Status: Open
Last updated: 2026-03-07
Severity: Medium

## Description

`sd_monitor.py` uses a global `process` variable to track the `frame_manager.py` subprocess. The SIGTERM signal handler calls `stop_frame_manager()` which modifies this global, but the main monitoring loop also reads/writes it. There's no locking, so concurrent access from the signal handler and main loop could cause:

- Double-kill of the subprocess
- Orphaned subprocess if the signal fires between check and assignment
- AttributeError if process is set to None mid-check

## Location

`eInkFrameWithStreamlitMananger/sd_monitor.py` — global `process` variable, `start_frame_manager()`, `stop_frame_manager()`, signal handler.

## Impact

In practice, this is unlikely to cause issues because SIGTERM only fires on service shutdown and the main loop sleeps most of the time. However, it's technically unsafe.

## Fix

Use `threading.Lock` around process access, or restructure to avoid globals (e.g., pass process handle through a context object).
