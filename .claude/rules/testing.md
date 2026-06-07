# Testing Standards

## Baseline

- Add tests when behavior changes.
- Keep tests deterministic and independent of production services.
- Use synthetic data only.
- Mock external LLMs, MCP connectors, and enterprise data sources unless running an explicit integration test.

## Test Types

- Unit tests for pure logic, parsing, routing, and policy decisions.
- Integration tests for API contracts, database access, queue behavior, and vector storage clients.
- Security tests for authorization, input validation, and secret handling.

## Coverage Expectations

- Critical security and authorization paths require direct tests.
- Shared utilities and contract transformations should have high coverage.
- Documentation-only changes do not require automated tests, but links and headings should be checked.

## Qdrant Demo

Run:

```bash
cd qdrant-multi-node-cluster
make test
```

Alternative:

```bash
cd qdrant-multi-node-cluster
python -m unittest discover -s tests
```

## Root Project Tests

Run synthetic unit tests offline:

```bash
python -m pytest -q
```

Run integration tests against live Docker services (PostgreSQL and Qdrant):

1. Spin up compose resources:
   ```bash
   docker compose up -d
   ```
2. Apply migrations:
   ```bash
   alembic -c infrastructure/alembic.ini upgrade head
   ```
3. Run with integration flag:
   ```bash
   # Windows PowerShell:
   $env:NEXUS_KB_RUN_LIVE_TESTS="1"
   python -m pytest tests/test_live_integration_scaffold.py -q

   # Linux/macOS:
   NEXUS_KB_RUN_LIVE_TESTS=1 python -m pytest tests/test_live_integration_scaffold.py -q
   ```
