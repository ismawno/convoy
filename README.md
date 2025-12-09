# Convoy

Convoy is a small collection of python scripts I have developed that help me with project maintainability, such as build or setup processes, especially in C/C++ projects. It mainly contains installation and code generation scripts that run at build time. It is not meant to be added as a git submodule or embedded in any way, but rather have the scripts you are interested in automatically copied to your target repositories using the utilities Convoy itself grants.

## Features
Convoy focuses in self contained scripts that can be run from the command line. It is not a library or a framework, but rather a collection of scripts that can be used to automate common tasks. The main features are:

- **Code generation**: Small scripts that help generating code at build time. Can be found in the [codegen](https://github.com/ismawno/convoy/tree/main/src/codegen) folder.

- **Build, Setup & Installation utilities**: The [setup](https://github.com/ismawno/convoy/tree/main/src/setup) folder contains scripts that help with the build and setup process of the project. This includes installing dependencies, setting up the environment, and generating configuration files. These scripts are designed for C/C++ projects.

Almost every script acts as a command line executable with parameters. Execute it with the `-h` or `--help` flag to see the available options and a small description of what they do.

### Build, Setup & Installation utilities

When creating projects, I like them to be easy to setup and build. With third-party software, however, this can become annoying, especially when not all dependency can be pulled automatically with `CMake`. And that assuming `CMake` itself is not missing, which is not as unusual (especially when I want non-programming friends to check out what I do). That is why the scripts under this section exist.

### Code generation utilities

Code generation is a recurring theme especially in languages where the program data is very inaccessible, such as C++. These utilities include generators (currently only C/C++ is supported) and parsers to inspect type information at compile time and generate code accordingly.

### Installation scripts

When it comes to installing required third party programs such as the `Vulkan SDK`, `CMake` or even `Visual Studio`, I would like those steps to be automated. The [setup.py](https://github.com/ismawno/convoy/blob/main/src/setup/setup.py) command line script does just that. It is a cross-platform installation script that can be used to install commonly required dependencies for graphics projects. I don't like obscure, non-localized build/installation scripts that install hundreds of dependencies without even asking, so I have designed these to be especially verbose and ask the user everytime a command is going to be issued through the terminal (this behaviour can be enabled/disabled with the appropiate arguments). It also supports uninstallation of the software it explicitly installed. Use the `-h` or `--help` flag to learn more about its capabilities.

### Building scripts

Because of how much I hate how the CMake cache works, I have also implemented some python building scripts in the [setup](https://github.com/ismawno/convoy/tree/main/src/setup) folder. The most relevant one is the [build.py](https://github.com/ismawno/convoy/blob/main/src/setup/build.py).

The reason behind this is that CMake sometimes stores some variables in cache that you may not want to persist. This results in some default values for variables being only relevant if the variable itself is not already stored in cache. The problem with this is that I feel it is very easy to lose track of what configuration is being built unless I type in all my CMake flags explicitly every time I build the project, and that is just unbearable. Hence, these python scripts provide flags with reliable defaults stored in a `build.ini` file that are always applied unless explicitly changed with a command line argument. This `build.ini` file can be generated automatically by another script, [cmake_scanner.py](https://github.com/ismawno/convoy/blob/main/src/setup/cmake_scanner.py), by scanning all `CMakeLists.txt` files and listing all build options defined with a little hint (specified with the `--hint` argument, see `-h` or `--help` to get more information) in a `build.ini` file. This generated file can be fully modified and contains generated documentation on how to do so effectively. It also supports overriding certain build options when other options are enabled/disabled (very handy when, for instance, asserts, warnings and logs should be disabled in distribution or release builds).
