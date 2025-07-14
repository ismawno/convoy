from pathlib import Path
from argparse import ArgumentParser, Namespace
from generator import CPPGenerator
from parser import CPParser, ControlMacros, Class
from collections.abc import Callable

import sys

sys.path.append(str(Path(__file__).parent.parent.parent))

from convoy import Convoy


class CPPOrchestrator:

    def __init__(
        self,
        rinputs: str | Path | list[str | Path],
        routputs: str | Path | list[str | Path],
        /,
        *parse_args,
        macros: ControlMacros | None = None,
        recursive: bool = False,
        file_per_class: bool = False,
        **parse_kwargs,
    ) -> None:

        self.__file_per_class = file_per_class
        inputs = Convoy.resolve_paths(
            rinputs, recursive=recursive, check_exists=True, require_files=True, remove_duplicates=True
        )
        outputs = Convoy.resolve_paths(
            routputs, recursive=recursive, require_single_type=True, mkdir=True, remove_duplicates=True
        )

        def log_paths(name: str, paths: list[Path], /) -> None:
            Convoy.verbose(f"Scanner resolved {len(paths)} {name} files.")
            for p in paths:
                Convoy.verbose(f" - <underline>{p}</underline>")

        log_paths("input", inputs)
        log_paths("output", outputs)

        parser = CPPOrchestrator.__create_parser(inputs, macros=macros)
        parser.remove_comments()
        if macros is not None and not parser.has_declare_macro():
            Convoy.verbose(
                f"The declare macro <bold>{macros.declare}</bold> was not found. No code will be generated."
            )
            self.__outputs = {}
            self.__generators = {}

        classes = parser.parse(*parse_args, **parse_kwargs)

        self.__outputs = self.__validate_and_resolve_outputs(inputs, outputs, classes)
        self.__generators = self.__create_generators()

    def generate(
        self, generator: Callable[[CPPGenerator, list[Class]], None], /, *, disclaimer: str | None = None
    ) -> None:
        for out, classes in self.__outputs.items():
            if not classes:
                continue
            gen = self.__generators[out]

            if disclaimer is not None:
                gen.disclaimer(disclaimer)
            gen("#pragma once")
            gen.include(str(out), quotes=True)

            generator(gen, classes)

            gen.write(out)

    @classmethod
    def from_cli_arguments(cls, args: Namespace, /, *, macros: ControlMacros | None = None):
        return cls(
            args.input, args.output, macros=macros, recursive=args.recursive, file_per_class=args.file_per_class
        )

    @classmethod
    def setup_cli_arguments(cls, parser: ArgumentParser, /, *, add_verbose: bool = False) -> None:
        parser.add_argument(
            "-i",
            "--input",
            type=Path,
            nargs="+",
            required=True,
            help="A path, list of path or pattern(s) for which all files contained will be scanned.",
        )
        parser.add_argument(
            "-o",
            "--output",
            type=Path,
            nargs="+",
            required=True,
            help="A path, list of paths or pattern(s) for which the generated code will be emitted. If the path is a folder, a file for each of the input files will be generated inside the specified folder, unless --file-per-class was specified. In that case, a file per scanned class or struct will be generated. If a pattern or list of paths is passed, it must be the same length as the number of inputs, and one file per input file will be emitted. If a single file path is passed, all emitted code will be written to that file.",
        )
        parser.add_argument(
            "-r",
            "--recursive",
            action="store_true",
            default=False,
            help="Whether to recursively search for input files in folders.",
        )
        parser.add_argument(
            "-f",
            "--file-per-class",
            action="store_true",
            default=False,
            help="Whether to generate a file per parsed class or struct. If selected, the output must be a single folder.",
        )
        if add_verbose:
            parser.add_argument(
                "-v",
                "--verbose",
                action="store_true",
                default=False,
                help="Print more information.",
            )

    def __create_generators(self) -> dict[Path, CPPGenerator]:
        return {out: CPPGenerator() for out in self.__outputs}

    def __validate_and_resolve_outputs(
        self, inputs: list[Path], outputs: list[Path], classes: list[Class], /
    ) -> dict[Path, list[Class]]:
        if not inputs or not outputs:
            Convoy.exit_error("Must at least provide an input and an output.")

        if len(outputs) == 1 and outputs[0].is_dir():
            odir = outputs[0]
            if self.__file_per_class:
                return CPPOrchestrator.__resolve_outputs_with_classes(classes, odir)

            return CPPOrchestrator.__resolve_outputs_with_inputs(classes, odir)

        if self.__file_per_class:
            Convoy.exit_error(
                "If the option <bold>--file-per-class</bold> is selected, the output must be a single directory"
            )

        if len(outputs) != 1:
            if len(inputs) != len(outputs):
                Convoy.exit_error("If multiple output paths are provided, they must match the amount of input files.")

            inp_to_out = {inp: out for inp, out in zip(inputs, outputs)}
            result: dict[Path, list[Class]] = {}
            for c in classes:
                if c.file is None:
                    Convoy.exit_error(f"The class <bold>{c.name}</bold> has no file attribute.")
                out = inp_to_out[c.file]
                result.setdefault(out, []).append(c)

            return result

        return {outputs[0]: classes}

    @classmethod
    def __resolve_outputs_with_classes(cls, classes: list[Class], directory: Path, /) -> dict[Path, list[Class]]:
        outputs = {}
        forbidden = r"<>:\"/\|?*"
        for c in classes:
            if any([f in c.name for f in forbidden]):
                Convoy.exit_error(
                    f"The class name <bold>{c.name}</bold> contains forbidden characters that cannot be used as a file name. To avoid this error, do not set the <bold>--file-per-class</bold> option and choose another way to export the generated code."
                )
            outputs[directory / c.name] = [c]

        return outputs

    @classmethod
    def __resolve_outputs_with_inputs(cls, classes: list[Class], directory: Path, /) -> dict[Path, list[Class]]:
        outputs: dict[Path, list[Class]] = {}
        for c in classes:
            if c.file is None:
                Convoy.exit_error(f"The class <bold>{c.name}</bold> has no file attribute.")
            outputs.setdefault(directory / c.file.name, []).append(c)

        return outputs

    @classmethod
    def __create_parser(cls, inputs: list[Path], /, *, macros: ControlMacros | None = None) -> CPParser:
        code = {}
        for inp in inputs:
            with open(inp, "r") as f:
                code[inp] = f.read()

        return CPParser(code, macros=macros)
