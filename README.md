# Convoy

Convoy is a small collection of python scripts I have developed that help me with my build/setup steps when developing a C/C++ program. It mainly contains installation and code generation scripts that run at build time. It is not meant to be added as a git submodule or embedded in any way, but rather have the script you are interested in automatically copied to your target repositories.

## Features
Convoy focuses in self contained scripts that can be run from the command line. It is not a library or a framework, but rather a collection of scripts that can be used to automate common tasks. The main features are:

- **Code generation**: Small scripts that help generating code at build time, such as reflection code. Can be found in the [codegen](https://github.com/ismawno/convoy/tree/main/src/codegen) folder.

- **Build, Setup & Installation utilities**: The [setup](https://github.com/ismawno/convoy/tree/main/src/codegen) folder contains scripts that help with the build and setup process of the project. This includes installing dependencies, setting up the environment, and generating configuration files.

Almost every script acts as a command line executable with parameters. Execute it with the `-h` or `--help` flag to see the available options and a small description of what they do.

### Code generation scripts

For me, one of the biggest missing features of C++ is reflection. This is a feature that allows you to inspect the structure of your code at runtime, and it is something that is available in many other languages. The code generation scripts in this repository are meant to help with this. They generate code that can be used to implement reflection in C++ by scanning `.hpp` or `.cpp` files of your choosing, and generating reflection code for every marked `class` or `struct` they see. The script [reflect.py](https://github.com/ismawno/toolkit/blob/main/codegen/reflect.py) is a command line script that is in charge of this functionality. Use the `-h` or `--help` flag to learn more about its capabilities.

### Build, Setup & Installation utilities

When creating projects, I like them to be easy to setup and build. With thrid-party software, however, this becomes challenging, specially when using system-wide SDKs (such as `Vulkan`) that are not so easy to install automatically through `CMake`. And that assuming `CMake` itself is not missing, which is not as unusual (specially when I want non-programming friends to check out what I do). That is why the scripts under this section exist.

#### Installation scripts

When it comes to installing required third party programs such as the `Vulkan SDK`, `CMake` or even `Visual Studio`, I would like those steps to be automated. The [setup.py](https://github.com/ismawno/convoy/blob/main/src/setup/setup.py) command line script does just that. It is a cross-platform installation script that can be used to install commonly required dependencies for C++ graphics projects. Use the `-h` or `--help` flag to learn more about its capabilities.

#### Building scripts

Because of how much I hate how the CMake cache works, I have also implemented some python building scripts in the [setup](https://github.com/ismawno/convoy/tree/main/src/setup) folder. The most relevant one is the [build.py](https://github.com/ismawno/convoy/blob/main/src/setup/build.py)

The reason behind this is that CMake sometimes stores some variables in cache that you may not want to persist. This results in some default values for variables being only relevant if the variable itself is not already stored in cache. The problem with this is that I feel it is very easy to lose track of what configuration is being built unless I type in all my CMake flags explicitly every time I build the project, and that is just unbearable. Hence, these python scripts provide flags with reliable defaults stored in a `build.ini` file that are always applied unless explicitly changed with a command line argument.