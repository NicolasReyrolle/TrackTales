---
description: "Use when creating a git commit or writing a pull request title. Covers the Conventional Commits policy enforced by commitizen and CI."
applyTo: "**"
---

# Commit Message Policy

- Use Conventional Commits for every commit message.
- Pull request titles must follow the Conventional Commits format, using the same allowed types and scope rules as commit messages.
- Allowed format: `<type>(<optional-scope>): <description>`.
- Common types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `ci`, `build`, `perf`, `revert`.
- Scope is optional; use a concise, relevant scope when helpful. Scope names are not restricted to a predefined list; omit the scope when none applies.
- Examples: `feat(ui): add trends period selector`, `fix(parser): guard empty route nodes`.
- For commits that revert earlier work, use the `revert` type in the required format (e.g. `revert(ui): undo trends period selector`). Do not keep Git's default `Revert "..."` subject line.
- Local enforcement is done with a `pre-commit` `commit-msg` hook (`commitizen`), and CI validates commit messages on every push and pull request.
