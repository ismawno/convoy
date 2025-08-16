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
        "--create-tag",
        type=Path,
        nargs="+",
        default=[],
        help="Create a new tag for all listed projects. The tag will be an increment following the --level parameter. The projects after the first are considered to require the previous one as a dependency, freezing cmake fetchcontent tag.",
    )
    parser.add_argument(
        "-l",
        "--level",
        type=str,
        nargs="+",
        default="fix",
        help="The level of the tag to increment. Can be 'fix', 'minor' or 'major'. Default is 'fix'.",
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
Convoy.program_label = "GIT"

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
        Convoy.warning(f"Skipping unmerged branch: <bold>{branch}</bold>.")
        return False

    for b in branches:
        if (
            any(re.search(pat, b) for pat in patterns)
            and check_merged(b)
            and Convoy.run_process_success(["git", "branch", "-D", b], cwd=cwd)
            and args.remote
        ):
            Convoy.run_process(["git", "push", "origin", "--delete", b], cwd=cwd, exit_on_decline=False)


projects: list[Path] = args.create_tag
if not projects:
    Convoy.exit_ok()


def modify_cmake(cmake: Path, old_tag: str, new_tag: str, parent_tag: str | None, /) -> bool:

    froze = parent_tag is not None
    if not cmake.is_file():
        Convoy.warning(f"The cmake path <underline>{cmake}</underline> is not a file or does not exist.")
        return False

    with open(cmake, "r") as f:
        content = f.read()
        froze = "GIT_TAG main" in content

    if froze:
        content = content.replace("GIT_TAG main", f"GIT_TAG {parent_tag}")
        Convoy.log(f"Modified <underline>{cmake}</underline> to freeze dependency to <bold>{parent_tag}</bold>.")
    else:
        Convoy.warning(f"A main branch reference was not found in <underline>{cmake}</underline>.")

    macro = rf"VERSION=\"{old_tag}" in content

    if macro:
        content = content.replace(rf"VERSION=\"{old_tag}", rf"VERSION=\"{new_tag}")
        Convoy.log(f"Modified <underline>{cmake}</underline> to update version macro.")
    else:
        Convoy.warning(f"Version macro with current tag <bold>{old_tag}</bold> not found.")

    if not froze and not macro:
        return False

    with open(cmake, "w") as f:
        f.write(content)

    if not Convoy.run_process_success(["git", "add", cmake.name], cwd=cmake.parent) or not Convoy.run_process_success(
        [
            "git",
            "commit",
            "-m",
            f"Freeze dependency to {parent_tag}" if parent_tag is not None else f"Update version macro to {new_tag}",
        ],
        cwd=cmake.parent,
    ):
        Convoy.exit_error(f"Failed to run git commands")

    return froze


def revert_cmake(cmake: Path, parent_tag: str, /) -> None:
    Convoy.log(f"Unfreezing at <bold>{cmake}</bold>.")
    with open(cmake.resolve(), "r") as f:
        content = f.read()

    content = content.replace(f"GIT_TAG {parent_tag}", "GIT_TAG main")
    Convoy.log(f"Modified <underline>{cmake}</underline> to unfreeze dependency from <bold>{parent_tag}</bold>.")
    with open(cmake, "w") as f:
        f.write(content)

    if not Convoy.run_process_success(["git", "add", cmake.name], cwd=cmake.parent) or not Convoy.run_process_success(
        ["git", "commit", "-m", f"Unfreeze dependency from {parent_tag}"], cwd=cmake.parent
    ):
        Convoy.exit_error(f"Failed to run git commands")


def increase_tag(tag: str, level: str, /) -> str:
    numbers = [int(n) for n in tag.strip("v").split(".")]
    if level == "major":
        return f"v{numbers[0] + 1}.0.0"
    if level == "minor":
        return f"v{numbers[0]}.{numbers[1] + 1}.0"
    return f"v{numbers[0]}.{numbers[1]}.{numbers[2] + 1}"


def biggest_tag(tags: str | list[str], /) -> str:
    if isinstance(tags, str):
        tags = tags.split("\n")

    map = {}
    for t in tags:
        if not t:
            continue

        numbers = [int(n) for n in t.strip("v").split(".")]
        score = numbers[0] * 1000000 + numbers[1] * 1000 + numbers[2]
        map[score] = t

    scores = sorted(map.keys())
    return map[scores[-1]]


def add_tag(project: Path, level: str, parent_tag: str | None = None, /) -> str:
    Convoy.log(f"Adding tag to project at <underline>{project}</underline>.")
    if not project.is_dir():
        Convoy.exit_error(f"The project <underline>{project}</underline> must exist and be a directory.")

    result = Convoy.run_process(
        ["git", "describe", "--tags", "--exact-match"],
        exit_on_decline=True,
        text=True,
        capture_output=True,
        cwd=project,
    )

    if result is not None and result.returncode == 0:
        tag = biggest_tag(result.stdout)
        Convoy.log(f"Found an already existing tag in the current commit: <bold>{tag}</bold>.")
        return tag

    result = Convoy.run_process(["git", "tag"], exit_on_decline=True, text=True, capture_output=True, cwd=project)
    if result is None:
        Convoy.exit_error("Failed to acquire tags.")

    tags: list[str] = [t for t in result.stdout.split("\n") if t]
    Convoy.log(f"Found tags: <bold>{', '.join(tags)}</bold>." if tags else "Found no tags.")

    old_tag = biggest_tag(tags) if tags else "v0.1.0"

    Convoy.log(f"Latest tag: <bold>{old_tag}</bold>.")

    result = Convoy.run_process(
        ["git", "log", "-1", "--pretty=%B"],
        exit_on_decline=True,
        text=True,
        capture_output=True,
        cwd=project,
    )
    if result is not None and "Unfreeze" in result.stdout:
        Convoy.log(f"Found an already existing compatible tag: <bold>{old_tag}</bold>.")
        return old_tag

    new_tag = increase_tag(old_tag, level)
    Convoy.log(f"Next tag: <bold>{new_tag}</bold>.")

    cmake = project / project.name / "CMakeLists.txt"
    froze = modify_cmake(cmake.resolve(), old_tag, new_tag, parent_tag)

    if not Convoy.run_process_success(["git", "tag", new_tag], cwd=project):
        Convoy.exit_error(f"Failed to create tag <bold>{new_tag}</bold>.")

    if froze and parent_tag is not None:
        revert_cmake(cmake, parent_tag)

    if not args.remote:
        return new_tag

    if not Convoy.run_process_success(
        ["git", "push", "origin", new_tag], cwd=project
    ) or not Convoy.run_process_success(["git", "push"], cwd=project):
        Convoy.exit_error("Failed to push.")

    return new_tag


levels = args.level
if len(levels) == 1:
    levels = levels * len(projects)

if len(levels) != len(projects):
    Convoy.exit_error("If not one, the number of levels must match the number of projects.")

tag = add_tag(projects[0].resolve(), levels[0])
for i in range(1, len(projects)):
    tag = add_tag(projects[i].resolve(), levels[0], tag)


Convoy.exit_ok()
