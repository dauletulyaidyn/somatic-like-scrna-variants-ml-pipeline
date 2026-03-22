# Contributing

This repository is kept intentionally clean. Use the workflow below for every code change.

## Branching
- `main` is the only permanent branch.
- Create a short, meaningful branch for each task.
- Examples:
  - `fix/status-reset`
  - `feat/gatk-runner`
  - `docs/manuscript-sync`

## Local workflow
1. Start from an up-to-date `main`.
2. Create a task branch.
3. Make focused changes.
4. Run the smallest relevant verification.
5. Commit with a meaningful message.
6. Push the branch.
7. Merge back into `main`.
8. Delete the task branch locally and on remote.

## Commit style
- Use short, concrete commit messages.
- Good:
  - `Fix stale status reset in Flask UI`
  - `Add GATK autonomous runner`
  - `Sync workflow docs with GATK pipeline`
- Avoid vague messages like:
  - `update`
  - `changes`
  - `fix stuff`

## Keep the repository clean
- Do not commit generated outputs.
- Do not commit large references, indexes, or run caches.
- Keep sample data and run artifacts outside git unless explicitly needed.
- Prefer updating docs together with code changes when behavior changes.

## Before push
- `git status` must be clean except for intended files.
- Confirm version changes if the behavior or release state changed.
- Confirm `README.md` still matches the current pipeline.

## When using Codex
If the instruction is `delai push`, the expected sequence is:
1. Create a meaningful branch.
2. Make a meaningful commit.
3. Push the branch.
4. Update the pipeline version and record it in `README.md`.
5. Verify the remote state.
6. Merge into `main`.
7. Delete the created branch locally and on remote.
