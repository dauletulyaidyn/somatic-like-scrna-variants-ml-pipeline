# Release Workflow

This document defines the release and push routine for this pipeline.

## Release rule
- `main` should always represent the cleanest publishable state.
- Every release or push-ready change must go through a short-lived branch.

## Standard push sequence
1. Sync `main` with remote.
2. Create a meaningful branch from `main`.
3. Make the code and documentation changes.
4. Bump the pipeline version if the repo state changed meaningfully.
5. Update:
   - `README.md`
   - `VERSION`
   - `config/pipeline_version.json`
   - `docs/CHANGELOG.md`
   - `docs/RELEASE_STATUS.md` when needed
6. Run targeted verification.
7. Commit with a meaningful message.
8. Push the branch.
9. Merge into `main`.
10. Push `main`.
11. Delete the short-lived branch locally and on remote.

## Versioning guidance
- Patch: small fixes without workflow changes.
- Minor/beta increment: new stage behavior, orchestration changes, documentation sync, or new validated capability.
- Major: incompatible structural change to the pipeline.

## Minimum release checklist
- `git status` is clean
- `main` and `origin/main` match after push
- `README.md` reflects current workflow
- release metadata files are updated
- temporary worktrees and throwaway branches are removed
- no generated outputs are left tracked

## Recommended verification
- `python -m py_compile` for touched Python scripts
- status UI starts clean
- autonomous runner help command works
- at least one smoke-test path is documented

## Cleanup expectation
After a successful push:
- keep only `main` as the permanent branch
- remove temporary worktrees
- remove short-lived remote branches
- keep any emergency backups outside the repository
