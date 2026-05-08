# ADR-003: Use Docker for background services

Date: 2026-05-08

## Status

Accepted

## Context

Email, HTTP, and logging alarms depend on network I/O and long-running processes. Running them inside the desktop app ties the UI lifecycle to network operations.

## Decision

Run email, HTTP, and logging in a separate Docker container.

## Consequences

Background services are isolated from the UI. The desktop app stays responsive regardless of network latency or failures. Docker must be installed on deployment machines (recorded as a BRS assumption). No GUI forwarding is needed because the container runs headless.