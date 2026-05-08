# ADR-006: Use YAML config with in-app settings UI

Date: 2026-05-08

## Status

Accepted

## Context

Alarm channels need to be toggled and configured (SMTP credentials, HTTP endpoint URL, etc.). Both manual and in-app editing should work.

## Decision

Use a YAML file as the single source of truth. The PySide6 UI reads it on startup and writes changes back.

## Consequences

Users edit settings through the UI or directly in the file. Automated deployments can pre-configure the file without launching the app. YAML is the standard config format across the Python ecosystem (Docker Compose, Ansible, most ML tools).

Rejected alternative: TOML (less familiar to most users).