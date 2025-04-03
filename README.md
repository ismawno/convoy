# Convoy

Convoy is a small collection of python scripts I have developed that help me with my build/setup steps when developing a C/C++ program. It mainly contains installation and code generation scripts that run at build time. It is not meant to be added as a git submodule or embedded in any way, but rather have the script you are interested in automatically copied to your target repositories.

## Features
Convoy focuses in self contained scripts that can be run from the command line. It is not a library or a framework, but rather a collection of scripts that can be used to automate common tasks. The main features are:

- **Code generation**: Small scripts that help generating code at build time, such as reflection code. Can be found in the [codegen](https://github.com/ismawno/convoy/blob/main/src/codegen) folder.

- **Setup & Installation utilities**: The [setup](https://github.com/ismawno/convoy/blob/main/src/codegen) folder contains scripts that help with the setup and installation of the project. This includes installing dependencies, setting up the environment, and generating configuration files.

Almost every script acts as a command line executable with parameters. Execute it with the `-h` or `--help` flag to see the available options and a small description of what they do.
