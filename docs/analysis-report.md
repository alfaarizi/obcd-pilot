# Analysis Report

Date: 2026-05-08

## 1 Tradeoff Analysis

### 1.1 ADR-001: Desktop UI Framework

**Decision:** Use PySide6.

| Criterion | Weight | PySide6 | Tkinter | PyQt6 | Electron |
|---|---|---|---|---|---|
| Cross-platform (Windows, macOS, Linux) | 0.25 | 9 | 9 | 9 | 9 |
| Widget coverage (forms, dialogs, media) | 0.20 | 9 | 4 | 9 | 9 |
| License compatibility | 0.20 | 9 (LGPL) | 10 (stdlib) | 4 (GPL) | 8 (MIT) |
| Bundle size impact | 0.15 | 5 (~150 MB) | 9 (stdlib) | 5 (~150 MB) | 2 (~300 MB) |
| Python integration and ecosystem | 0.20 | 9 | 7 | 9 | 3 |
| **Weighted total** | | **8.40** | **7.80** | **7.40** | **6.55** |

PySide6 wins on widget coverage, license safety, and Python ecosystem fit. Tkinter scores well on size but lacks the widgets the app needs. PyQt6 ties on features but carries GPL risk. Electron is too heavy.

### 1.2 ADR-002: Application Packaging

**Decision:** Use PyInstaller.

| Criterion | Weight | PyInstaller | cx_Freeze | Nuitka | pip install |
|---|---|---|---|---|---|
| No developer tools required on target | 0.30 | 9 | 9 | 9 | 2 |
| Cross-platform support | 0.25 | 9 | 7 | 7 | 9 |
| Community and documentation maturity | 0.20 | 9 | 5 | 6 | 10 |
| Compatibility with PyTorch and PySide6 | 0.15 | 7 | 5 | 6 | 10 |
| Build time and complexity | 0.10 | 6 | 6 | 4 | 10 |
| **Weighted total** | | **8.40** | **6.80** | **6.95** | **7.35** |

PyInstaller leads because it produces a standalone binary on all three OSes and has the largest community for troubleshooting freeze issues. pip install scores high on compatibility but fails the "no developer tools" requirement, which carries the most weight.

### 1.3 ADR-003: Background Service Isolation

**Decision:** Run email, HTTP, and logging in a Docker container.

| Criterion | Weight | Docker container | In-process | OS system service |
|---|---|---|---|---|
| UI lifecycle isolation | 0.30 | 10 | 2 | 8 |
| Cross-platform deployment | 0.25 | 8 | 10 | 4 |
| Network failure resilience | 0.20 | 9 | 4 | 8 |
| Deployment complexity | 0.15 | 5 | 10 | 3 |
| Reproducibility | 0.10 | 10 | 7 | 5 |
| **Weighted total** | | **8.55** | **6.10** | **5.95** |

Docker wins on isolation and resilience. The desktop app stays responsive even when the SMTP server is slow or the HTTP endpoint is down. In-process is simpler to deploy but ties the UI to network I/O. OS system services differ too much across platforms.

### 1.4 ADR-004: Desktop-to-Docker Communication

**Decision:** Use REST (HTTP POST).

| Criterion | Weight | REST (FastAPI) | gRPC | Message queue | Unix sockets |
|---|---|---|---|---|---|
| Cross-platform (including Windows) | 0.30 | 10 | 10 | 10 | 3 |
| Simplicity and testability | 0.25 | 9 | 5 | 4 | 7 |
| Dependency overhead | 0.20 | 8 | 4 (protobuf) | 3 (broker) | 9 |
| Debuggability (curl, browser, logs) | 0.15 | 10 | 4 | 5 | 4 |
| Performance for one-to-one localhost | 0.10 | 8 | 10 | 7 | 9 |
| **Weighted total** | | **9.15** | **6.65** | **6.05** | **5.95** |

REST wins by a wide margin. For a one-to-one localhost link, the simplicity and debuggability of HTTP POST outweigh the performance advantage of gRPC or sockets. Unix sockets fail on Windows entirely.

### 1.5 ADR-005: Pipeline Threading Model

**Decision:** Run the OBCD pipeline in a QThread with Qt signals.

| Criterion | Weight | QThread + signals | multiprocessing | asyncio |
|---|---|---|---|---|
| UI responsiveness during inference | 0.30 | 9 | 9 | 5 |
| GIL compatibility (PyTorch/OpenCV release GIL) | 0.25 | 9 | 10 | 4 |
| PyInstaller packaging compatibility | 0.20 | 9 | 5 | 9 |
| IPC complexity | 0.15 | 9 (signals) | 4 (pipes/queues) | 7 |
| PySide6 official pattern alignment | 0.10 | 10 | 3 | 5 |
| **Weighted total** | | **9.10** | **7.10** | **5.85** |

QThread wins because PyTorch and OpenCV release the GIL during their C++ computations, so a thread is enough to keep the UI responsive. multiprocessing scores well on GIL handling but adds IPC overhead and makes PyInstaller packaging harder. asyncio cannot offload CPU-bound inference.

### 1.6 ADR-006: Configuration Format

**Decision:** Use YAML.

| Criterion | Weight | YAML | TOML | JSON | INI |
|---|---|---|---|---|---|
| Human readability and editability | 0.30 | 9 | 8 | 5 | 7 |
| Ecosystem familiarity (Docker Compose, ML tools) | 0.25 | 9 | 6 | 8 | 4 |
| UI round-trip (read, edit, write back) | 0.20 | 8 | 7 | 9 | 6 |
| Nested structure support | 0.15 | 9 | 8 | 9 | 3 |
| Schema validation tooling | 0.10 | 6 | 7 | 9 | 3 |
| **Weighted total** | | **8.50** | **7.20** | **7.55** | **5.05** |

YAML wins on readability and ecosystem fit. Users already know it from Docker Compose and ML config files. JSON scores close on structure and validation but is harder for humans to edit by hand. INI cannot express nested config.

## 2 Risk Register

| ID | Risk | Probability | Impact | Mitigation | Status |
|---|---|---|---|---|---|
| RSK-001 | PyTorch and PySide6 bundled via PyInstaller push the distributable past 2 GB. | High | High | Quantize models. Evaluate lazy download of weights on first launch. Measure bundle size in a Sprint 1 spike. | Open |
| RSK-002 | PyInstaller fails to freeze PyTorch or PySide6 correctly on one or more OS. | Medium | High | Run a freeze test on all three OSes in Sprint 1. Maintain PyInstaller hook overrides. | Open |
| RSK-003 | Webcam API behaves differently across Windows, macOS, and Linux (device indices, permissions, frame formats). | High | Medium | Use the OpenCV VideoCapture abstraction. Test on all three OSes. Add OS-specific fallback paths if needed. | Open |
| RSK-004 | QThread pipeline assumes PyTorch and OpenCV release the GIL; if they hold it, the UI freezes. | Low | High | Verify GIL release with a profiling spike in Sprint 1. If the GIL is held, fall back to multiprocessing and supersede ADR-005. | Open |
| RSK-005 | Docker is not installed on the target machine, so email, HTTP, and logging alarms cannot run. | Medium | Medium | Document Docker as a prerequisite. Provide a fallback mode that runs background services in-process with a warning. | Open |
| RSK-006 | SMTP credentials are wrong or the server is unreachable, causing silent email alarm failures. | Medium | Medium | Add a "test connection" button in the settings UI. Log SMTP errors with RFC 5321 response codes. Surface failures as a UI notification. | Open |
| RSK-007 | Firewall or security software on the target machine blocks the REST endpoint on localhost. | Low | Medium | Use a high, non-standard port. Document firewall exceptions in user docs. | Open |
| RSK-008 | Inference latency exceeds the 2-second detection requirement (US-01, AC-01.1) on CPU-only machines. | Medium | High | Benchmark inference in Sprint 1 on CPU. If too slow, evaluate ONNX Runtime export or model quantization. Define minimum hardware spec in user docs. | Open |