from pathlib import Path
from argparse import ArgumentParser, Namespace
from dataclasses import dataclass, field
from collections.abc import Callable

import sys
import copy
import xml.etree.ElementTree as ET
import difflib

from cppgen import CPPFile

sys.path.append(str(Path(__file__).parent.parent))

from convoy import Convoy


def parse_arguments() -> Namespace:
    desc = """
    The purpose of this script is to generate the code needed to load all available vulkan functions and organize
    them in such a way that it is clear which functions/structs are available and which are not.
    """

    parser = ArgumentParser(description=desc)
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        default=None,
        help="The input path where the 'vk.xml' file is located. If not provided, the script will download the file.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        help="The output file path where the generated code will be saved.",
    )
    parser.add_argument(
        "-a",
        "--api",
        type=str,
        default="vulkan",
        help="The API to generate code for. Can be 'vulkan' or 'vulkansc'.",
    )
    parser.add_argument(
        "--guard-version",
        action="store_true",
        default=False,
        help="If set, the generated code will be guarded by the VKIT_API_VERSION macro when necessary.",
    )
    parser.add_argument(
        "--guard-extension",
        action="store_true",
        default=False,
        help="If set, the generated code will be guarded by extension macros when necessary.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=False,
        help="Print more information.",
    )

    return parser.parse_args()


@dataclass
class GuardGroup:
    guards: list[list[str]] = field(default_factory=list)

    def and_guards(self, guards: str | list[str], /) -> None:
        if isinstance(guards, str):
            guards = [guards]
        guards = [g.strip() for g in guards]
        self.guards.append([f"defined({g})" if " " not in g else g for g in guards])

    def parse_guards(self) -> str:
        if not self.guards:
            return ""

        or_guards: list[str] = []
        for group in self.guards:
            or_guards.append(" || ".join(group))

        return " && ".join(
            [f"({g})" if "||" in g else g for g in or_guards if g]
        ).strip()


broken_functions = {
    "vkGetLatencyTimingsNV": 271,  # Changed API parameters
    "vkCmdSetDiscardRectangleEnableEXT": 241,  # new function in older extension
    "vkCmdSetDiscardRectangleModeEXT": 241,  # new function in older extension
    "vkCmdSetExclusiveScissorEnableNV": 241,  # Changed API parameters
    "vkCmdInitializeGraphScratchMemoryAMDX": 298,  # Changed API parameters
    "vkCmdDispatchGraphAMDX": 298,  # Changed API parameters
    "vkCmdDispatchGraphIndirectAMDX": 298,  # Changed API parameters
    "vkCmdDispatchGraphIndirectCountAMDX": 298,  # Changed API parameters
}


@dataclass
class Function:
    name: str
    return_type: str
    params: list[str]
    param_types: list[str]
    dispatchable: bool
    available_since: str | None = None
    guards: list[GuardGroup] = field(default_factory=list)

    def parse_guards(self) -> str:
        guards = [g.parse_guards() for g in self.guards]
        guards = " || ".join([f"({g})" if "&&" in g else g for g in guards if g])

        if self.name not in broken_functions:
            return guards.strip()

        hv = f"VK_HEADER_VERSION >= {broken_functions[self.name]}"
        return hv if not guards else f"{hv} && ({guards})".strip()

    def as_string(
        self,
        *,
        namespace: str | None = None,
        vk_prefix: bool = True,
        no_discard: bool = False,
        api_macro: bool = False,
        semicolon: bool = True,
        noexcept: bool = False,
    ) -> str:
        params = ", ".join(
            f"{param_type} {param_name}"
            for param_type, param_name in zip(self.param_types, self.params)
        )
        name = self.name if vk_prefix else self.name.removeprefix("vk")
        if namespace is not None:
            name = f"{namespace}::{name}"

        rtype = self.return_type
        if no_discard and rtype != "void":
            rtype = f"[[nodiscard]] {rtype}"
        if api_macro:
            rtype = f"VKIT_API {rtype}"
        noexcept = " noexcept" if noexcept else ""

        return (
            f"{rtype} {name}({params}){noexcept};"
            if semicolon
            else f"{rtype} {name}({params}){noexcept}"
        )

    def as_fn_pointer_declaration(
        self, *, modifier: str | None = None, null: bool = False
    ) -> str:
        if modifier is None:
            modifier = ""
        return (
            f"{modifier} PFN_{self.name} {self.name};".strip()
            if not null
            else f"{modifier} PFN_{self.name} {self.name} = VK_NULL_HANDLE;".strip()
        )

    def as_fn_pointer_type(self) -> str:
        return f"PFN_{self.name}"

    def is_instance_function(self) -> bool:
        return (
            fn.name
            not in [
                "vkGetInstanceProcAddr",
                "vkCreateInstance",
                "vkDestroyInstance",
            ]
            and self.dispatchable
            and (
                self.param_types[0] == "VkInstance"
                or self.param_types[0] == "VkPhysicalDevice"
            )
        )

    def is_device_function(self) -> bool:
        return (
            fn.name not in ["vkGetDeviceProcAddr", "vkCreateDevice", "vkDestroyDevice"]
            and self.dispatchable
            and self.param_types[0] != "VkInstance"
            and self.param_types[0] != "VkPhysicalDevice"
        )


def download_vk_xml() -> Path:
    import urllib.request

    url = "https://raw.githubusercontent.com/KhronosGroup/Vulkan-Docs/refs/heads/main/xml/vk.xml"

    vendor = root / "vendor"
    vendor.mkdir(exist_ok=True)

    location = vendor / "vk.xml"
    if location.exists():
        return location

    try:
        urllib.request.urlretrieve(url, str(location))
        Convoy.verbose(
            f"Downloaded <bold>vk.xml</bold> from <underline>{url}</underline> to <underline>{location}</underline>."
        )
    except Exception as e:
        Convoy.exit_error(
            f"Failed to download <bold>vk.xml</bold> from <underline>{url}</underline> because of <bold>{e}</bold>. Please download it manually and place it in <underline>{location}</underline>, or provide the path with the <bold>-i</bold> or <bold>--input</bold> argument."
        )

    return location


Convoy.log_label = "VK-LOADER"
root = Path(__file__).parent.resolve()

args = parse_arguments()
Convoy.is_verbose = args.verbose
vulkan_api: str = args.api

vkxml_path: Path | None = args.input
output: Path = args.output.resolve()

if vkxml_path is None:
    vkxml_path = download_vk_xml()

vkxml_path = vkxml_path.resolve()

with open(vkxml_path, "r") as f:
    vkxml = f.read()

tree = ET.ElementTree(ET.fromstring(vkxml))
root = tree.getroot()

dispatchables: set[str] = set()
for h in root.findall("types/type[@category='handle']"):
    text = "".join(h.itertext())
    if "VK_DEFINE_HANDLE" in text:
        name = h.get("name") or h.find("name").text
        dispatchables.add(name)

functions: dict[str, Function] = {}

for command in root.findall("commands/command"):
    proto = command.find("proto")
    if proto is None:
        continue

    name = proto.find("name").text
    return_type = proto.find("type").text

    api = command.get("api")
    if api is not None and vulkan_api not in api.split(","):
        continue

    params = []
    param_types = []
    for param in command.findall("param"):
        api = param.get("api")
        if api is not None and vulkan_api not in api.split(","):
            continue

        param_name = param.find("name").text
        full = "".join(param.itertext()).strip()
        param_type = full.rsplit(param_name, 1)[0].strip()

        params.append(param_name)
        param_types.append(param_type)

    fn = Function(
        name,
        return_type,
        params,
        param_types,
        param_types and param_types[0] in dispatchables,
    )
    functions[name] = fn
    Convoy.verbose(f"Parsed vulkan function <bold>{fn.as_string()}</bold>.")

type_aliases: dict[str, list[str]] = {}
for tp in root.findall("types/type"):
    alias = tp.get("alias")
    if alias is None:
        continue
    name = tp.get("name")

    type_aliases.setdefault(alias, []).append(name)

for command in root.findall("commands/command"):
    alias = command.get("alias")
    if alias is None:
        continue

    name = command.get("name")
    if name in functions:
        continue

    fn = copy.deepcopy(functions[alias])
    fn.name = name
    for i, fntp in enumerate(fn.param_types):
        clean_fntp = (
            fntp.replace("const", "").replace("*", "").replace("struct", "").strip()
        )
        if clean_fntp not in type_aliases:
            continue

        tpal = type_aliases[clean_fntp]
        closest = difflib.get_close_matches(name, tpal, n=1, cutoff=0.0)[0]
        fn.param_types[i] = fntp.replace(clean_fntp, closest)

    functions[name] = fn

Convoy.log(
    f"Found <bold>{len(functions)}</bold> {vulkan_api} functions in the vk.xml file."
)


for feature in root.findall("feature"):
    version = feature.get("name")

    for require in feature.findall("require"):

        types = require.findall("type")
        for command in require.findall("command"):
            fname = command.get("name")
            fn = functions[fname]
            if fn.available_since is not None:
                Convoy.exit_error(
                    f"Function <bold>{fname}</bold> is already flagged as required since <bold>{fn.available_since}</bold>. Cannot register it again for the <bold>{version}</bold> feature."
                )

            fn.available_since = version
            guards = GuardGroup()
            if version != "VK_VERSION_1_0" and args.guard_version:
                guards.and_guards(version)

            fn.guards.append(guards)
            Convoy.verbose(
                f"Registered availability of function <bold>{fname}</bold> from the <bold>{version}</bold> feature."
            )

spec_version_req = {
    "vkCmdSetDiscardRectangleEnableEXT": 2,
    "vkCmdSetDiscardRectangleModeEXT": 2,
    "vkCmdSetExclusiveScissorEnableNV": 2,
    "vkGetImageViewAddressNVX": 2,
    "vkGetImageViewHandle64NVX": 3,
    "vkGetDeviceSubpassShadingMaxWorkgroupSizeHUAWEI": 2,
}

for extension in root.findall("extensions/extension"):
    extname = extension.get("name")
    for require in extension.findall("require"):
        guards = GuardGroup()
        if args.guard_extension:
            guards.and_guards(extname)

        deps = require.get("depends")
        if deps is not None and args.guard_extension:
            for group in deps.split("+"):
                guards.and_guards(group.split(","))

        for command in require.findall("command"):
            fname = command.get("name")
            if fname in spec_version_req and args.guard_version:
                guards.and_guards(
                    f"{extname.upper()}_SPEC_VERSION >= {spec_version_req[fname]}"
                )
            functions[fname].guards.append(guards)
            Convoy.verbose(
                f"Registered availability of function <bold>{name}</bold> from the <bold>{name}</bold> extension."
            )


def guard_if_needed(
    code: CPPFile, text: str | Callable, guards: str, /, *args, **kwargs
) -> None:
    def put_code() -> None:
        if isinstance(text, str):
            code(text)
        else:
            text(code, *args, **kwargs)

    if guards:
        code(f"#if {guards}", indent=0)
        put_code()
        code("#endif", indent=0)
    else:
        put_code()


hpp = CPPFile("loader.hpp")
hpp.disclaimer("vkloader.py")
hpp.include("vkit/vulkan/vulkan.hpp", quotes=True)


with hpp.scope("namespace VKit", indent=0):
    hpp.spacing()

    hpp("#if defined(TKIT_OS_APPLE) || defined(TKIT_OS_LINUX)", indent=0)
    hpp("void Load(void *p_Library);")
    hpp("#else", indent=0)
    hpp("void Load(HMODULE p_Library);")
    hpp("#endif", indent=0)
    hpp.spacing()

    def code(code: CPPFile, fn: Function, /) -> None:
        code(fn.as_fn_pointer_declaration(modifier="extern"))
        code(
            fn.as_string(
                vk_prefix=False, no_discard=True, api_macro=True, noexcept=True
            )
        )

    for fn in functions.values():
        if fn.is_instance_function() or fn.is_device_function():
            continue
        guards = fn.parse_guards()

        guard_if_needed(hpp, code, guards, fn)
        hpp.spacing()

    hpp.spacing()

    def code(code: CPPFile, fn: Function, /) -> None:
        code(fn.as_fn_pointer_declaration(null=True))
        code(fn.as_string(vk_prefix=False, no_discard=True, noexcept=True))

    with hpp.scope("struct VKIT_API InstanceFunctions", closer="};"):
        hpp("InstanceFunctions Create(VkInstance p_Instance);")
        for fn in functions.values():
            if not fn.is_instance_function():
                continue

            guards = fn.parse_guards()
            guard_if_needed(hpp, code, guards, fn)
            hpp.spacing()

    with hpp.scope("struct VKIT_API DeviceFunctions", closer="};"):
        hpp("DeviceFunctions Create(VkDevice p_Device);")
        for fn in functions.values():
            if not fn.is_device_function():
                continue

            guards = fn.parse_guards()
            guard_if_needed(hpp, code, guards, fn)
            hpp.spacing()


cpp = CPPFile("loader.cpp")
cpp.disclaimer("vkloader.py")
cpp.include("vkit/core/pch.hpp", quotes=True)
cpp.include((output / "loader.hpp").resolve(), quotes=True)
cpp.include("tkit/utils/logging.hpp", quotes=True)

with cpp.scope("namespace VKit", indent=0):

    with cpp.scope(
        "template <typename T> static T validateFunction(const char *p_Name, T &&p_Function)"
    ):
        cpp(
            "TKIT_ASSERT(p_Function, \"The function '{}' is not available for the device being used.\", p_Name);"
        )
        cpp("return p_Function;")

    def code(code: CPPFile, fn: Function, /) -> None:
        code(fn.as_fn_pointer_declaration(modifier="static", null=True))
        with code.scope(fn.as_string(vk_prefix=False, semicolon=False, noexcept=True)):
            code(
                f'static {fn.as_fn_pointer_type()} fn = validateFunction("{fn.name}", TKit::{fn.name});'
            )
            if fn.return_type != "void":
                code(f"return fn({', '.join(fn.params)});")
            else:
                code(f"fn({', '.join(fn.params)});")

    cpp.spacing()
    for fn in functions.values():
        if fn.is_instance_function() or fn.is_device_function():
            continue
        guards = fn.parse_guards()
        guard_if_needed(cpp, code, guards, fn)

    cpp.spacing()
    cpp("#if defined(TKIT_OS_APPLE) || defined(TKIT_OS_LINUX)", indent=0)
    cpp("void Load(void *p_Library)")
    cpp("#else", indent=0)
    cpp("void Load(HMODULE p_Library)")
    cpp("#endif", indent=0)

    with cpp.scope():
        cpp("#if defined(TKIT_OS_APPLE) || defined(TKIT_OS_LINUX)", indent=0)
        cpp(
            's_vkGetInstanceProcAddr = reinterpret_cast<PFN_vkGetInstanceProcAddr>(dlsym(p_Library, "vkGetInstanceProcAddr"));'
        )
        cpp("#else", indent=0)
        cpp(
            's_vkGetInstanceProcAddr = reinterpret_cast<PFN_vkGetInstanceProcAddr>(GetProcAddress(p_Library, "vkGetInstanceProcAddr"));'
        )
        cpp("#endif", indent=0)

        cpp.spacing()
        for fn in functions.values():
            if (
                fn.name == "vkGetInstanceProcAddr"
                or fn.is_instance_function()
                or fn.is_device_function()
            ):
                continue
            guards = fn.parse_guards()
            guard_if_needed(
                cpp,
                f'{fn.name} = reinterpret_cast<{fn.as_fn_pointer_type()}>(s_vkGetInstanceProcAddr(VK_NULL_HANDLE, "{fn.name}"));',
                guards,
            )
    cpp.spacing()
    with cpp.scope(
        "InstanceFunctions InstanceFunctions::Create(const VkInstance p_Instance)"
    ):
        cpp("InstanceFunctions functions{};")
        for fn in functions.values():
            if not fn.is_instance_function():
                continue
            guards = fn.parse_guards()
            guard_if_needed(
                cpp,
                f'functions.{fn.name} = reinterpret_cast<{fn.as_fn_pointer_type()}>(s_vkGetInstanceProcAddr(p_Instance, "{fn.name}"));',
                guards,
            )
        cpp("return functions;")

    cpp.spacing()
    with cpp.scope("DeviceFunctions DeviceFunctions::Create(const VkDevice p_Device)"):
        cpp("DeviceFunctions functions{};")
        for fn in functions.values():
            if not fn.is_device_function():
                continue
            guards = fn.parse_guards()
            guard_if_needed(
                cpp,
                f'functions.{fn.name} = reinterpret_cast<{fn.as_fn_pointer_type()}>(s_vkGetInstanceProcAddr(p_Device, "{fn.name}"));',
                guards,
            )
        cpp("return functions;")

    def code(code: CPPFile, fn: Function, /, *, namespace: str) -> None:
        with code.scope(
            fn.as_string(
                vk_prefix=False, semicolon=False, noexcept=True, namespace=namespace
            )
        ):
            code(
                f'static {fn.as_fn_pointer_type()} fn = validateFunction("{fn.name}", this->{fn.name});'
            )
            if fn.return_type != "void":
                code(f"return fn({', '.join(fn.params)});")
            else:
                code(f"fn({', '.join(fn.params)});")

    cpp.spacing()
    for fn in functions.values():
        if not fn.is_instance_function():
            continue
        guards = fn.parse_guards()
        guard_if_needed(
            cpp,
            code,
            guards,
            fn,
            namespace="InstanceFunctions",
        )

    cpp.spacing()
    for fn in functions.values():
        if not fn.is_device_function():
            continue
        guards = fn.parse_guards()
        guard_if_needed(
            cpp,
            code,
            guards,
            fn,
            namespace="DeviceFunctions",
        )

hpp.write(output)
cpp.write(output)

Convoy.exit_ok()
