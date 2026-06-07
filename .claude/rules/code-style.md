# Code Style

## General

- Favor simple, explicit code over clever abstractions.
- Keep public APIs typed and documented.
- Use clear names that describe domain behavior.
- Keep generated artifacts out of source control.

## TypeScript

- Use strict TypeScript when TypeScript code is added.
- Define explicit return types for exported functions.
- Avoid `any`; use `unknown` and narrow it.
- Prefer `interface` for object contracts shared across module boundaries.

## Python

- Follow PEP 8.
- Use type hints for public functions and methods.
- Prefer small modules with explicit dependencies.
- Use structured exceptions and avoid silent failure.

## Documentation

- Keep architecture terms consistent with `docs/architecture.md`.
- Avoid claims that are not backed by implementation or tests.
- Use public-safe examples only.

## Comments

- Explain why a non-obvious decision exists.
- Avoid comments that restate code.
