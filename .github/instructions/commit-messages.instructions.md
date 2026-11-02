---
description: "Use when creating a git commit or writing a pull request title. Covers the Conventional Commits policy enforced by commitizen and CI."
applyTo: "**"
excludeAgent: "code-review"
---

# Commit Message Policy

- Use Conventional Commits for every commit message.
- Pull request titles should also follow Conventional Commits format to enable automated changelog generation.
- Allowed format: `<type>(<optional-scope>): <description>`.
- For breaking changes, append `!` after the type or scope (e.g. `feat(api)!: remove v1 endpoints`) and add a footer line starting with `BREAKING CHANGE:` that describes the change.
- Allowed types (exhaustive, must match the commitizen config): `build`, `chore`, `ci`, `docs`, `feat`, `fix`, `perf`, `refactor`, `revert`, `style`, `test`.
- Do not use any type not in this list.
- Examples: `feat(ui): add trends period selector`, `fix(parser): guard empty route nodes`.
- Do not create commits with non-conventional messages.
- If a requested commit message does not match the required format, rewrite it to the closest valid `<type>(<optional-scope>): <description>` form, tell the user the rewritten message, and commit only after confirmation. If the correct type cannot be determined, ask the user which type to use before committing.
- Local enforcement is done with a `pre-commit` `commit-msg` hook (`commitizen`), and CI validates commit messages on every push and pull request.
