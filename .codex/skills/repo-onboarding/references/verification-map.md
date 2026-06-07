# Verification Map

- Documentation changes:
  - Check internal links.
  - Check headings and source-of-truth consistency.
  - Confirm no private data, secret, or local runtime state is documented as committed content.
- Qdrant demo changes:
  - `cd qdrant-multi-node-cluster`
  - `make test`
  - If `make` is unavailable, run `python -m unittest discover -s tests`.
- Agent configuration changes:
  - Confirm referenced files exist.
  - Confirm local-only files are ignored by `.gitignore`.
  - Confirm rules do not require private tooling for open-source contribution.
