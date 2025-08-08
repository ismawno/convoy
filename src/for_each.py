from argparse import ArgumentParser, Namespace
from pathlib import Path
from convoy import Convoy


def parse_arguments() -> Namespace:
    desc = """This python scripts executes multiple commands from different
    working directories. Useful when managing multiple projects and must, for example 'git push' all of them."""

    parser = ArgumentParser(description=desc)
    parser.add_argument(
        "-c",
        "--cmds",
        "--commands",
        type=str,
        required=True,
        nargs="+",
        help="The commands to execute.",
    )
    parser.add_argument(
        "-d",
        "--directories",
        required=True,
        nargs="+",
        type=Path,
        help="The directories to execute the command in.",
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
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        default=False,
        help="Recursively execute the command.",
    )
    parser.add_argument(
        "--skip-if-missing",
        action="store_true",
        default=False,
        help="Skip directories that do not exist instead of failing.",
    )
    parser.add_argument(
        "--ignore-cmd-errors",
        action="store_true",
        default=False,
        help="Ignore any errors that occur while executing the command.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=False,
        help="Print more information.",
    )
    parser.add_argument(
        "-n",
        "--nested",
        action="store_true",
        default=False,
        help="Instead of trying to match directories and commands 1-to-1, apply all commands to all directories.",
    )

    return parser.parse_args()


Convoy.program_label = "FOR-EACH"
args = parse_arguments()
if args.safe and args.yes:
    Convoy.exit_error("The <bold>-s</bold> and <bold>-y</bold> flags cannot be used together.")

Convoy.safe = args.safe
Convoy.all_yes = args.yes
Convoy.is_verbose = args.verbose
cmds: list[str] = args.cmds
directories = Convoy.resolve_paths(
    args.directories,
    recursive=args.recursive,
    require_directories=True,
    remove_duplicates=True,
    check_exists=not args.skip_if_missing,
)
Convoy.verbose(f"Resolved {len(directories)} input directories:")
for dir in directories:
    Convoy.verbose(f" - <underline>{dir}</underline>")

if not args.nested:
    if len(cmds) == 1:
        cmds *= len(directories)
    if len(cmds) != len(directories):
        Convoy.exit_error(
            f"The number of commands provided must match the number of directories provided if the former is more than one. Commands: <bold>{', '.join(cmds)} ({len(cmds)})</bold>, Directories: <bold>{', '.join([str(dir) for dir in directories])} ({len(directories)})</bold>."
        )

wdir = Path.cwd()


def process_directory(path: Path, cmd: str, /) -> None:
    if not path.exists():
        Convoy.warning(f"Skipping missing directory: <underline>{path}</underline>")
        return

    Convoy.verbose(f"Executing command <bold>{cmd}</bold> at <underline>{path}</underline>.")
    if not Convoy.run_process_success(cmd, cwd=path, shell=True, log=False):
        if not args.ignore_cmd_errors:
            Convoy.exit_error(f"Failed to execute command <bold>{cmd}</bold> at <underline>{path}</underline>.")
        Convoy.warning(f"Command <bold>{cmd}</bold> failed at <underline>{path}</underline>.")


if not args.nested:
    for dir, cmd in zip(directories, cmds):
        process_directory(dir, cmd)
else:
    for dir in directories:
        for cmd in cmds:
            process_directory(dir, cmd)
