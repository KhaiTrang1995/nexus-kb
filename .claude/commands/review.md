# /project:review

## Usage

```text
/project:review [file or diff]
```

## Purpose

Run a structured code review focused on defects and project risk.

## Review Priorities

1. Correctness: logic errors, edge cases, concurrency risks, and data loss.
2. Security: OWASP risks, exposed secrets, unsafe auth, missing authorization checks.
3. Architecture: drift from `docs/architecture.md` or layer boundary violations.
4. Performance: N+1 queries, unbounded payloads, avoidable LLM or vector calls.
5. Tests: missing regression coverage or weak verification.

## Output Format

Return findings first, ordered by severity:

- Critical: must fix before merge.
- High: likely production or security risk.
- Medium: meaningful correctness, maintainability, or testing gap.
- Low: minor issue or improvement.

Include file and line references when available. If no issues are found, say that directly and mention residual test gaps.

## Suggested Inspection

```bash
git diff --stat
git diff
```
