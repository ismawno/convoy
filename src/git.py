from argparse import ArgumentParser, Namespace
from pathlib import Path
from convoy import Convoy

import subprocess
import re


def parse_arguments() -> Namespace:
    desc = """This python script has different git utilities."""
    parser = ArgumentParser(description=desc)

    parser.add_argument(
        "-p",
        "--path",
        type=Path,
        default=None,
        help="The working directory from which to execute the commands. Defaults to current working directory.",
    )
    parser.add_argument(
        "--remove-branches",
        type=str,
        nargs="*",
        default=None,
        help="Remove git branches according to specific patterns.",
    )
    parser.add_argument(
        "--protected-branches",
        type=str,
        nargs="*",
        default=["main", "master", "dev"],
        help="Prevent changes to the listed branches.",
    )
    parser.add_argument(
        "-r", "--remote", action="store_true", default=False, help="Apply changes on remote as well, when applicable."
    )
    parser.add_argument(
        "-s",
        "--safe",
        action="store_true",
        default=False,
        help="Prompt before executing commands. This setting cannot be used with the '-y' flag.",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        default=False,
        help="Skip all prompts and proceed with everything.",
    )

    return parser.parse_args()


args = parse_arguments()
if args.safe and args.yes:
    Convoy.exit_error("The <bold>-s</bold> and <bold>-y</bold> flags cannot be used together.")
Convoy.safe = args.safe
Convoy.all_yes = args.yes
Convoy.log_label = "GIT"

cwd = args.path
if cwd is not None:
    cwd = cwd.resolve()


def get_branches() -> list[str]:
    branches = Convoy.ncheck(
        Convoy.run_process(["git", "branch"], stdout=subprocess.PIPE, text=True, cwd=cwd),
        msg="Failed to retrieve git branches",
    )
    if not branches.returncode == 0:
        Convoy.exit_error("Failed to retrieve git branches")
    return [
        b.lstrip("* ")
        for b in branches.stdout.split("\n")
        if b != "" and b.lstrip("* ") not in args.protected_branches
    ]


def get_merged_branches(target: str = "main", /) -> list[str]:
    branches = Convoy.ncheck(
        Convoy.run_process(["git", "branch", "--merged", target], stdout=subprocess.PIPE, text=True, cwd=cwd),
        msg="Failed to retrieve git branches",
    )
    if not branches.returncode == 0:
        Convoy.exit_error("Failed to retrieve git branches")
    return [b.lstrip("* ") for b in branches.stdout.split("\n") if b != ""]


if args.remove_branches is not None:
    patterns: list[str] = args.remove_branches
    if not patterns:
        patterns = [".*"]

    branches = get_branches()
    merged = get_merged_branches()

    def check_merged(branch: str, /) -> bool:
        if branch in merged:
            return True
        Convoy.log(f"<fyellow>Skipping unmerged branch: <bold>{branch}</bold>.")
        return False

    for b in branches:
        if (
            any(re.search(pat, b) for pat in patterns)
            and check_merged(b)
            and Convoy.run_process_success(["git", "branch", "-D", b], cwd=cwd)
            and args.remote
        ):
            Convoy.run_process(["git", "push", "origin", "--delete", b], cwd=cwd, exit_on_decline=False)

Convoy.exit_ok()
