# ADR-004: Use REST for desktop-to-Docker communication

Date: 2026-05-08

## Status

Accepted

## Context

The desktop app needs to tell the Docker container "a change was detected, fire the remote alarms." The connection is one-to-one over localhost.

## Decision

Use REST (HTTP POST) per RFC 9110. The background service exposes an endpoint via FastAPI.

## Consequences

REST on localhost is simple, cross-platform, and testable with curl. No extra dependencies beyond FastAPI and an HTTP client.

Rejected alternatives: gRPC (unnecessary protobuf overhead), message queues (extra dependency for a one-to-one link), Unix sockets (broken on Windows).