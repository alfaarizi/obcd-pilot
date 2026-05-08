# ADR-001: Use PySide6 for the desktop UI

Date: 2026-05-08

## Status

Accepted

## Context

The app needs a cross-platform native GUI framework with Python bindings. It must run on Windows, macOS, and Linux.

## Decision

Use PySide6.

## Consequences

PySide6 is LGPL-licensed and officially supported by Qt. It covers the full widget set for desktop apps but adds about 150 MB to the distributable. It also requires Qt event loop integration with async code.

Rejected alternatives: Tkinter (limited widgets), PyQt6 (GPL licensing risk), Electron (heavy runtime).