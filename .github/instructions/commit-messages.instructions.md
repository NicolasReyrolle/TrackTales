---
description: "Use when creating a git commit or writing a pull request title. Covers the Conventional Commits policy enforced by commitizen and CI."
---

# Commit Message Policy

- Use Conventional Commits for every commit message.
- Pull request titles should also follow Conventional Commits format to enable automated changelog generation.
- Allowed format: `<type>(<optional-scope>): <description>`.
- Common types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `ci`, `build`, `perf`, `revert`.
- Examples: `feat(ui): add trends period selector`, `fix(parser): guard empty route nodes`.
- Do not create commits with non-conventional messages.
- Local enforcement is done with a `pre-commit` `commit-msg` hook (`commitizen`), and CI validates commit messages on every push and pull request.
