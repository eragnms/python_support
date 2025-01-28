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
        "python_support@git+https://git@github.com/eragnms/python_support.git@main"
    ]

To use for example the configuration module do:

    from python_support.configuration import MyConfig  # type: ignore

## Modules

### PushoverMessage

Will send messages to the Pushover service. Create an account on
https://pushover.net/ and create an app and take note of its token.
The user_key (shown once one has logged in at pushover.net) and the
token shall be given to this class at time of initialization.
Install the Pushover app on your phone to receive messages on it.

### MyConfig

This is a module that will read a configuration file on the "INI"
format and will make it possible to access its settings as attributes.

The configuration file name shall be defined in the environment
variable "env_var" on the system that runs the application. The "env_var"
should be passed at initialization of the class MyConfig.

#### Example

Configuration file:

    [SECTION]
    key = value

Python script:

    from python_support.configuration import MyConfig
    config = MyConfig("PATH_TO_CONFIG_FILE")
    print(config.section_key)

### MyLogger

This module will create and configure a logger with console and
(optional) file logging. If you don't want to log to a file, just
leave "log_file" empty. If "add_timestamp" is set to True when
the class is initialized then a timestamp will be added to all
log entries. Default is no timestamps.

#### Example

The example uses argparse.

In the main file:

    import argparse
    import logging
    from python_support.logging import MyLogger

    LOGGER_NAME = "MY_LOGGER"
    log = logging.getLogger(LOGGER_NAME)

    def main() -> None:
        parser = argparse.ArgumentParser(
            description="See README and project documentation for details."
        )
        parser.add_argument(
            "--loglevel",
            "-l",
            default="INFO",
            choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            help="Set the logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
        )
        args = parser.parse_args()
        if args.loglevel:
            numeric_level = getattr(logging, args.loglevel.upper(), None)
            if not isinstance(numeric_level, int):
                raise ValueError("Invalid log level: %s" % args.loglevel)
            level = numeric_level
        MyLogger(add_timestamp=True).setup_logger(level, LOGGER_NAME, "/tmp/my_log.log")
        log.info("This is a INFO log message")

In another file in the same project:

    import logging

    log = logging.getLogger("MY_LOGGER")


    class MyClass:
        def __init__(self):
            log.debug("This is a DEBUG log message")
