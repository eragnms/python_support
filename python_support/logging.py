"""Setup a nice logger"""

import logging

import colorlog  # type: ignore


class MyLogger:
    """Class to handle miscellaneous tools."""

    def __init__(self, add_timestamp: bool = False):
        """
        Initialize the MyLogger instance.

        :param add_timestamp: If True, prepend a timestamp to each log entry.
        """
        self.add_timestamp = add_timestamp

    def setup_logger(
        self, level: int, logger_name: str, log_file: str | None = None
    ) -> None:
        """Create and configure a logger with console, optional file logging.

        Do (at the top of your script):
        import logging
        log = logging.getLogger(logger_name)

        Then (at the beginning of your script):
        MyLogger(add_timestamp=True).setup_logger(level, logger_name, log_file)

        log_file is optional. If you don't want to log to a file, just leave it empty.

        Example using argparse:

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
        numeric_level = getattr(logging, args.loglevel.upper(), None)
        if not isinstance(numeric_level, int):
           raise ValueError("Invalid log level: %s" % args.loglevel)
        level = numeric_level
        MyLogger(add_timestamp=True).setup_logger(level, LOGGER_NAME)
        """
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)
        # Clear existing handlers to avoid duplicates
        if logger.hasHandlers():
            logger.handlers.clear()

        # Define the log format
        if self.add_timestamp:
            # Include timestamp at the beginning
            format_prefix = "%(asctime)s "
            datefmt = "%Y-%m-%d %H:%M:%S"
        else:
            format_prefix = ""
            datefmt = None

        # Create a color formatter (console)
        if level == logging.DEBUG:
            text = (
                format_prefix + "%(log_color)s%(name)s(%(filename)s:%(lineno)d) - "
                "%(levelname)s: %(message)s"
            )
        else:
            text = format_prefix + "%(log_color)s%(levelname)s: %(message)s"

        formatter = colorlog.ColoredFormatter(
            text,
            datefmt=datefmt,
            log_colors={
                "DEBUG": "reset",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "bold_red",
            },
            secondary_log_colors={},
            style="%",
        )

        # Create and configure console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # Create and configure file handler
        if log_file is not None and log_file != "":
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        # Prevent log messages from being propagated to higher level loggers
        logger.propagate = False
