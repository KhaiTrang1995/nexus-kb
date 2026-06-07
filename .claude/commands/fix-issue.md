# /project:fix-issue

## Usage

```text
/project:fix-issue <issue-id or description>
```

## Workflow

1. Reproduce or understand the failure.
2. Locate the smallest relevant file set.
3. Apply the minimal fix.
4. Add or update regression coverage when behavior changes.
5. Run the most relevant verification command.
6. Summarize root cause, fix, and verification.

## Verification

For Qdrant demo changes:

```bash
cd qdrant-multi-node-cluster
make test
```

For documentation-only changes, manually check links, headings, and source-of-truth consistency.

## Constraints

- Follow `.claude/rules/`.
- Do not refactor unrelated code.
- Do not commit secrets, logs, sessions, raw documents, model files, or generated data.
