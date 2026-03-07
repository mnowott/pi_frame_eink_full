# B-005: Unused gpiozero import in sd_monitor.py

Status: Closed
Last updated: 2026-03-07
Severity: Low

## Description

`sd_monitor.py` imports `gpiozero` but never uses it. This adds an unnecessary dependency and causes import errors on non-Pi systems.

## Location

`eInkFrameWithStreamlitMananger/sd_monitor.py` — top-level import.

## Fix

Remove the unused import.
