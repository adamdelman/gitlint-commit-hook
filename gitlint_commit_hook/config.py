from pathlib import Path

RULES_DIR = Path(__file__).parent / "rules"
JIRA_KEY = r"[A-Z][A-Z0-9_]+-\d+"
BASE_IGNORED_RULES = ["body-min-length", "body-is-missing"]
RULES_IGNORED_FOR_MERGES = [
    "title-max-length",
    "title-imperative-mood",
    "title-capitalized",
    "title-match-regex",
    "title-trailing-punctuation",
    "body-max-line-length",
    "body-min-length",
    "body-is-missing",
]


def build_config(require_jira_prefix: bool, require_pr_number_on_merge: bool) -> str:
    """
    Build the gitlint config

    :param require_jira_prefix: Require a Jira key (e.g. "OCPSG-123: ") in commit titles
    :param require_pr_number_on_merge: Require a PR number ("#123") in merges into
        master, main, dev or develop
    :return: The contents of a gitlint config file
    """
    # The rule is always loaded from RULES_DIR, so it is ignored unless it is required
    ignored = BASE_IGNORED_RULES + ([] if require_pr_number_on_merge else ["merge-requires-pr-number"])
    # gitlint skips fixup!, squash!, amend! and revert commits on its own, but not once a Jira key
    # is in front (e.g. added by merge-issue-number-hook)
    skipped_prefixed = [r"(fixup|squash|amend)! ", 'Revert "']
    if not require_pr_number_on_merge:
        skipped_prefixed.append("Merge ")

    lines = [
        "[general]",
        f"ignore={','.join(ignored)}",
        f"extra-path={RULES_DIR}",
        "regex-style-search=true",
    ]
    if require_pr_number_on_merge:
        # merge-requires-pr-number checks merges; the other rules skip them (see ignore-by-title:merges)
        lines.append("ignore-merge-commits=false")
    lines += ["", "[title-max-length]", "line-length=72"]
    if require_jira_prefix:
        lines += ["", "[title-match-regex]", f"regex=^{JIRA_KEY}:"]
    lines += ["", "[body-max-line-length]", "line-length=72"]
    # A URL or a Co-authored-by trailer stops working if it is wrapped
    lines += ["", "[ignore-body-lines]", r"regex=(?i)^(\s*https?://\S+\s*|co-authored-by: .*)$"]
    if require_pr_number_on_merge:
        lines += [
            "",
            "[merge-requires-pr-number]",
            "long-lived-branches=master,main,dev,develop",
            "",
            "[ignore-by-title:merges]",
            # git writes merge messages; a hook such as merge-issue-number-hook may add a Jira key
            rf"regex=^({JIRA_KEY}: )?Merge",
            # Replaces the [general] ignore list for these commits, so those rules are listed again
            f"ignore={','.join(RULES_IGNORED_FOR_MERGES)}",
        ]
    lines += [
        "",
        "[ignore-by-title]",
        f"regex=^{JIRA_KEY}: ({'|'.join(skipped_prefixed)})",
        "ignore=all",
        "",
    ]
    return "\n".join(lines)
