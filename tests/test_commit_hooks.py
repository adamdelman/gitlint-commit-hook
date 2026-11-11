import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
import yaml

REPO_DIR = Path(__file__).parent.parent
ISOLATED_GIT_ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": os.devnull,
    # gitlint --staged needs a git identity
    "GIT_CONFIG_COUNT": "2",
    "GIT_CONFIG_KEY_0": "user.name",
    "GIT_CONFIG_VALUE_0": "t",
    "GIT_CONFIG_KEY_1": "user.email",
    "GIT_CONFIG_VALUE_1": "t@example.com",
    "PYTHONPATH": str(REPO_DIR),
}


def dedent_block(text: str) -> str:
    return textwrap.dedent(text).lstrip("\n")


@pytest.fixture(scope="module")
def project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A scratch git repo with no gitlint config of its own"""
    path = tmp_path_factory.mktemp("project")
    subprocess.run(["git", "init", "-q"], cwd=path, check=True, env=ISOLATED_GIT_ENV)
    return path


def lint(project: Path, message: str, *flags: str) -> tuple[int, str]:
    message_file = project / ".git" / "TEST_MSG"
    message_file.write_text(message)
    gitlint = [sys.executable, "-m", "gitlint_commit_hook", *flags, str(message_file)]
    result = subprocess.run(
        gitlint, cwd=project, capture_output=True, text=True, env=ISOLATED_GIT_ENV
    )
    return result.returncode, result.stderr


@pytest.mark.parametrize(
    "message",
    [
        pytest.param("Add x\n", id="title-only"),
        pytest.param(
            dedent_block(
                """
                Process files

                Why this matters.
                """
            ),
            id="explained",
        ),
        pytest.param("Embed schema\n", id="stemmer-exception"),
        pytest.param("Bring back retries\n", id="verb-ending-in-ing"),
        pytest.param("Add a title that is a little over fifty characters\n", id="title-of-50"),
        pytest.param("OCPSG-1: Add x\n", id="jira-prefix"),
        pytest.param("OCPSG-1386: OCPSG-700: Add x\n", id="two-jira-prefixes"),
        pytest.param(
            dedent_block(
                """
                Fix command injection

                https://github.com/org/repo/pull/1254#discussion_r4119826451
                """
            ),
            id="long-url-line",
        ),
        pytest.param(
            dedent_block(
                """
                Bump version

                Co-authored-by: mssalvatore <19957806+mssalvatore@users.noreply.github.com>
                """
            ),
            id="long-co-authored-by-line",
        ),
        pytest.param(
            "Merge branch 'OCPSG-1292-automatically-add-release-notes-and-many-more-words'\n",
            id="long-merge-title",
        ),
        pytest.param("Merged stuff\n", id="merge-like-title"),
        pytest.param("OCPSG-1: Merge branch 'master' into x\n", id="jira-prefixed-merge"),
        pytest.param("OCPSG-1: fixup! OCPSG-1: Add x\n", id="jira-prefixed-fixup"),
        pytest.param(
            dedent_block(
                """
                OCPSG-1: amend! OCPSG-1: Add x

                OCPSG-1: Add x better
                """
            ),
            id="jira-prefixed-amend",
        ),
        pytest.param(
            dedent_block(
                """
                OCPSG-1: Revert "OCPSG-1: Add x"

                This reverts commit abc.
                """
            ),
            id="jira-prefixed-revert",
        ),
    ],
)
def test_gitlint__accepts_valid_message(project: Path, message: str) -> None:
    assert lint(project, message) == (0, "")


@pytest.mark.parametrize(
    "message, rule",
    [
        pytest.param(
            "Add a title that is definitely way over the seventy-two character limit imposed by gitlint\n",
            "T1",
            id="long-title",
        ),
        pytest.param("Add x.\n", "T3", id="trailing-period"),
        pytest.param("add map writer\n", "UL2", id="lowercase-title"),
        pytest.param("OCPSG-1: add map writer\n", "UL2", id="lowercase-after-jira-key"),
        pytest.param("Added x\n", "UL1", id="past-tense-known-verb"),
        pytest.param("Bumped x\n", "UL1", id="past-tense-unknown-verb"),
        pytest.param("OCPSG-1386: OCPSG-700: Removed ACR login\n", "UL1", id="past-after-two-keys"),
        pytest.param("Initial commit\n", "UL1", id="not-a-verb"),
        pytest.param("Add x\nBody right under the title.\n", "B4", id="no-blank-line"),
        pytest.param(
            dedent_block(
                """
                Add x

                This explanation keeps on running until it ends up past the seventy-two limit.
                """
            ),
            "B1",
            id="long-prose-line",
        ),
    ],
)
def test_gitlint__rejects_invalid_message(project: Path, message: str, rule: str) -> None:
    returncode, stderr = lint(project, message)
    assert returncode != 0
    assert rule in stderr


def test_pre_commit_hooks__entry_takes_message_file_last() -> None:
    # pre-commit runs `entry <args from the consumer's config> <message file>`
    config = yaml.safe_load((REPO_DIR / ".pre-commit-hooks.yaml").read_text())
    hooks = {hook["id"]: hook for hook in config}
    assert hooks["gitlint"]["entry"] == "gitlint-commit-hook"
    assert "args" not in hooks["gitlint"]


@pytest.mark.parametrize(
    "flags, unprefixed_returncode",
    [((), 0), (("--require-jira-prefix",), 1)],
    ids=["off", "on"],
)
def test_require_jira_prefix(
    project: Path, flags: tuple[str, ...], unprefixed_returncode: int
) -> None:
    assert lint(project, "OCPSG-1: Add x\n", *flags) == (0, "")
    returncode, stderr = lint(project, "Add x\n", *flags)
    assert returncode == unprefixed_returncode
    assert ("T7" in stderr) == bool(flags)


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, capture_output=True, check=True, env=ISOLATED_GIT_ENV)


def commit(repo: Path, message: str) -> None:
    git(repo, "commit", "-q", "--allow-empty", "--no-verify", "-m", message)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A clone with a feature branch that has diverged from master"""
    repo = tmp_path / "demo"
    repo.mkdir()
    git(tmp_path, "init", "-q", "--bare", "origin.git")
    for args in (
        ["init", "-q", "-b", "master"],
        ["config", "user.email", "t@example.com"],
        ["config", "user.name", "t"],
        ["remote", "add", "origin", str(tmp_path / "origin.git")],
    ):
        git(repo, *args)
    commit(repo, "Add project")
    git(repo, "push", "-q", "-u", "origin", "master")
    git(repo, "checkout", "-q", "-b", "OCPSG-1-x")
    commit(repo, "Add x")
    git(repo, "checkout", "-q", "master")
    commit(repo, "Add y")
    return repo


PR_FLAG = "--require-pr-number-on-merge"


def test_merge_into_master__requires_pr_number(repo: Path) -> None:
    git(repo, "merge", "-q", "--no-ff", "--no-commit", "OCPSG-1-x")
    returncode, stderr = lint(repo, "Merge branch 'OCPSG-1-x'\n", PR_FLAG)
    assert returncode != 0
    assert "UC1" in stderr
    assert lint(repo, "Merge branch 'OCPSG-1-x'\n\nPR #42\n", PR_FLAG) == (0, "")
    assert lint(repo, "OCPSG-1: Merge pull request #42 from org/OCPSG-1-x\n", PR_FLAG) == (0, "")


def test_merge_into_master__needs_no_pr_number_by_default(repo: Path) -> None:
    git(repo, "merge", "-q", "--no-ff", "--no-commit", "OCPSG-1-x")
    assert lint(repo, "Merge branch 'OCPSG-1-x'\n") == (0, "")


def test_merge_into_feature_branch__needs_no_pr_number(repo: Path) -> None:
    git(repo, "checkout", "-q", "OCPSG-1-x")
    git(repo, "merge", "-q", "--no-ff", "--no-commit", "master")
    assert lint(repo, "Merge branch 'master' into OCPSG-1-x\n", PR_FLAG) == (0, "")


def test_pull_on_master__needs_no_pr_number(repo: Path) -> None:
    git(repo, "push", "-q", "origin", "master")
    git(repo, "reset", "-q", "--hard", "HEAD~1")
    commit(repo, "Add z")
    git(repo, "merge", "-q", "--no-ff", "--no-commit", "origin/master")
    assert lint(repo, "Merge branch 'master' of github.com:org/demo\n", PR_FLAG) == (0, "")


def test_require_pr_number_on_merge__ordinary_commit_needs_no_pr_number(repo: Path) -> None:
    assert lint(repo, "Add z\n", PR_FLAG) == (0, "")
