import argparse
import tempfile
from pathlib import Path

from gitlint.cli import cli

from gitlint_commit_hook.config import build_config


def main() -> None:
    """Lint a commit message file with gitlint, using this package's config and rules"""
    parser = argparse.ArgumentParser(description="Lint a commit message with gitlint")
    parser.add_argument(
        "--require-jira-prefix",
        action="store_true",
        help="Require a Jira key (e.g. 'OCPSG-123: ') in commit titles",
    )
    parser.add_argument(
        "--require-pr-number-on-merge",
        action="store_true",
        help="Require a PR number ('#123') in merges into master, main, dev or develop",
    )
    parser.add_argument("message_file", help="The commit message file, as given by pre-commit")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        config = Path(tmp) / "gitlint.ini"
        config.write_text(build_config(args.require_jira_prefix, args.require_pr_number_on_merge))
        cli.main(args=["-C", str(config), "--staged", "--msg-filename", args.message_file])


if __name__ == "__main__":
    main()
