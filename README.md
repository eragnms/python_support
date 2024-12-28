# python_support
A repository for my support python modules

## Usage

Install Directly from GitHub: Use the following command to install the package via pip:

    pip install git+ssh://git@github.com/eragnms/python_support.git@main

Add to requirements.txt

If you want to include python_support as a dependency in your project,
add it to your requirements.txt file:

    git+ssh://git@github.com/eragnms/python_support.git@main

Add to pyproject.toml (if your project uses it)

If your other project also uses pyproject.toml, you can include python_support in
the [project.dependencies] section:

    [project]
    dependencies = [
        "git+ssh://git@github.com/<your-username>/python_support.git@main"
    ]

To use for example the configuration module do:

    from python_support.configuration import MyConfig  # type: ignore

## Modules

For more information on the modules see the comments in their source files.

- configuration.MyConfig
- logging.MyLoggin
