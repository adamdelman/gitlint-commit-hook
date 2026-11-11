# gitlint commit hook

A [pre-commit](https://pre-commit.com) hook that lints commit messages with
[gitlint](https://jorisroovers.com/gitlint/), following the rules of
[How to Write a Git Commit Message](https://cbea.ms/git-commit) that a linter can check:

- Separate the subject from the body with a blank line.
- Keep the subject at most 72 characters long.
- Capitalize the subject.
- Don't end the subject with a period.
- Use the imperative mood in the subject (`Add`, not `Added` or `Adds`).
- Wrap the body at 72 characters. URLs and `Co-authored-by:` lines are exempt.

```text
Add map writer

Explain what changed and why, not how.
```

Merges, fixups, squashes, amends and `git revert` commits are not checked, also when a Jira key
such as `OCPSG-123: ` is in front of the subject.

## Usage

Add the hook to your `.pre-commit-config.yaml` and make pre-commit install the `commit-msg` hook:

```yaml
default_install_hook_types: [pre-commit, commit-msg]

repos:
  - repo: https://github.com/adamdelman/gitlint-commit-hook
    rev: v0.1.0
    hooks:
      - id: gitlint
```

Then run `pre-commit install` once in each clone. The hook uses its own gitlint config, so a
`.gitlint` in your project is ignored.

### Options

Two optional checks, both off by default. Turn them on with `args`:

```yaml
      - id: gitlint
        args: [--require-jira-prefix, --require-pr-number-on-merge]
```

- `--require-jira-prefix`: the subject must start with a Jira key, e.g. `OCPSG-123: `.
- `--require-pr-number-on-merge`: merges into `master`, `main`, `dev` or `develop` must contain a
  PR number (`#123`). Merges into other branches and `git pull` merges don't need one. A
  fast-forward makes no commit, so it can't be checked; use `git merge --no-ff`. With this option
  merges are no longer skipped by the other rules' exemption, but they are still not checked for
  title length, mood, capitalization, punctuation or body line length.

## Development

```bash
poetry install
pre-commit install
poetry run pytest
```
