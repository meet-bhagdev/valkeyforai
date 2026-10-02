# Testing the Build Workflow Locally

The GitHub Actions workflow in `.github/workflows/build.yml` regenerates the
cookbook artifacts and keeps them in sync with the Markdown source. This page
explains what that workflow does and how to reproduce each part of it locally
before you open a pull request.

## What the workflow does

The workflow defines one `build` job that runs on `ubuntu-latest`. It triggers
on pushes to `main` and on pull requests, scoped by `paths` filters to the
content and build files so unrelated changes do not run it.

| Step | Command | Purpose |
| --- | --- | --- |
| Check out | `actions/checkout@v4` | Clone the repository with a token that allows pushing back |
| Set up Node | `actions/setup-node@v4` | Install Node.js 20 |
| Install dependencies | `npm ci` | Install from `package-lock.json` for a reproducible tree |
| Build artifacts | `npm run build` | Generate `cookbooks/` HTML and `notebooks/` from `content/` |
| Validate notebooks | `npm run check:notebooks` | Fail on missing, stale, or orphan notebooks |
| Check for changes | `git status --porcelain -- cookbooks/ notebooks/` | Detect uncommitted generated output |
| Require artifacts (PR) | gated on `pull_request` | Fail the PR if generated artifacts are stale |
| Commit and push (main) | gated on `push` | Auto-commit regenerated artifacts as `github-actions[bot]` |

The key contract is the **change check**: after a clean build, the generated
`cookbooks/` and `notebooks/` trees must match what is committed. On a pull
request the workflow fails if they differ, which is its way of telling you to
run `npm run build` and commit the output. On a push to `main` the workflow
commits the regenerated artifacts for you.

## Option 1 — Run the steps directly (recommended)

The job is a sequence of npm scripts, so you can reproduce it exactly from the
repository root. This is the fastest path and the one to use day to day.

```bash
npm ci                                        # reproducible install
npm run build                                 # build:html + build:notebooks
npm run check:notebooks                        # validate notebook coverage
git status --porcelain -- cookbooks/ notebooks/   # should print nothing
```

If the final command prints anything after a clean build, that is exactly what
the pull-request gate fails on. Stage and commit the regenerated artifacts:

```bash
git add cookbooks/ notebooks/
git commit -m "Regenerate cookbook artifacts"
```

As a single pre-flight check before pushing:

```bash
npm ci && npm run build && npm run check:notebooks \
  && git status --porcelain -- cookbooks/ notebooks/
```

A clean run with no trailing `git status` output means the pull-request check
will pass.

## Option 2 — Run the workflow with `act`

[`act`](https://github.com/nektos/act) runs GitHub Actions locally inside
Docker. Use it when you are changing the workflow YAML itself and want to verify
the job logic end to end, rather than just the npm scripts.

```bash
brew install act          # requires a running Docker daemon
```

```bash
act -n                    # dry run: print the execution plan only
act pull_request          # simulate a pull_request event
act push                  # simulate a push to main
act -j build              # run just the build job
```

Notes for this repository:

- Use `act pull_request` to exercise the validation path. The commit-and-push
  step is gated on `github.event_name == 'push'`, so a pull-request run skips
  it and avoids a failing `git push`.
- `act push` runs the auto-commit step, whose `git push` fails locally because
  there is no authenticated remote. That failure is expected.
- On Apple Silicon, add `--container-architecture linux/amd64` if images fail
  to run.
- `secrets.GITHUB_TOKEN` does not exist locally. Pass a dummy value when a step
  needs it: `act -s GITHUB_TOKEN=dummy`.

## Option 3 — Lint the workflow file

[`actionlint`](https://github.com/rhysd/actionlint) checks the workflow for
YAML, syntax, and expression errors without running anything.

```bash
brew install actionlint
actionlint .github/workflows/build.yml
```

This is a fast first check after editing the workflow and catches mistakes that
`act` would only surface at run time.

## Which option to use

| Situation | Use |
| --- | --- |
| Edited a cookbook or build script | Option 1 — run the npm scripts |
| Verifying the PR artifact gate before pushing | Option 1 — the one-line pre-flight check |
| Changed `.github/workflows/build.yml` logic | Option 2 — `act` |
| Quick syntax check of the workflow file | Option 3 — `actionlint` |

For everyday cookbook work, Option 1 reproduces the entire meaningful part of
the workflow. Reach for `act` only when the workflow definition itself changes.
