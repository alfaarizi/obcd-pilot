# Definition of Done

Date: 2026-05-09

1. Code passes `ruff check` (88-char line length) and `mypy --strict` with zero errors.
2. Unit tests pass with ≥ 90% branch coverage (`pytest --cov --cov-branch`).
3. Integration tests pass for every module boundary the change touches.
4. Every public class, method, and function has a PEP 257 docstring.
5. Every function signature carries PEP 484 type hints.
6. Static analysis reports no new high or critical findings.
7. For release sprints, verified on Windows, macOS, and Linux. For all other sprints, verified on at least one target platform.
8. User-facing changes reflected in user documentation.