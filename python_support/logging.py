"""Setup a nice logger with optional systemd journal support."""

from __future__ import annotations

import logging
from logging.handlers import SysLogHandler

import colorlog  # type: ignore

# Try to use systemd's native journal handler if available.
try:
    from systemd.journal import JournalHandler  # type: ignore

    _HAS_JOURNAL = True
except Exception:
    JournalHandler = None
    _HAS_JOURNAL = False


class MyLogger:
    """Class to handle miscellaneous tools."""

    def __init__(self, add_timestamp: bool = False):
        """
        Initialize the MyLogger instance.

        :param add_timestamp: If True, prepend a timestamp to each log entry.
        """
        self.add_timestamp = add_timestamp

    def setup_logger(
        self,
        level: int,
        logger_name: str,
        log_file: str | None = None,
        *,
        log_to_journal: bool = False,
        journal_identifier: str | None = None,
        log_console: bool = True,
    ) -> None:
        """Create and configure a logger with console, optional file, and
        optional journal logging.

        Do (at the top of your script):
        import logging
        log = logging.getLogger(logger_name)

        Then (at the beginning of your script):
        MyLogger(add_timestamp=True).setup_logger(level, logger_name, log_file)

        log_file is optional. If you don't want to log to a file, just leave it empty.

        Then (at the beginning of your script):
        MyLogger(add_timestamp=True).setup_logger(
            level, logger_name, log_file,
            log_to_journal=True,
            journal_identifier="dldp-scan",
        )

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
            console_text = (
                format_prefix + "%(log_color)s%(name)s(%(filename)s:%(lineno)d) - "
                "%(levelname)s: %(message)s"
            )
        else:
            console_text = format_prefix + "%(log_color)s%(levelname)s: %(message)s"

        color_formatter = colorlog.ColoredFormatter(
            console_text,
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

        # Plain (no color) formatter for file/journal
        if level == logging.DEBUG:
            plain_text = (
                format_prefix + "%(name)s(%(filename)s:%(lineno)d) - "
                "%(levelname)s: %(message)s"
            )
        else:
            plain_text = format_prefix + "%(levelname)s: %(message)s"
        plain_formatter = logging.Formatter(plain_text, datefmt=datefmt)

        # Create and configure console handler (stdout/stderr)
        # NOTE: When running under systemd with StandardOutput=journal,
        # this ends up in journalctl. Set log_console=False to suppress.
        if log_console:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(color_formatter)
            logger.addHandler(console_handler)

        # Create and configure file handler
        if log_file is not None and log_file != "":
            file_handler = logging.FileHandler(log_file)
            # Avoid ANSI color codes in files
            file_handler.setFormatter(plain_formatter)
            logger.addHandler(file_handler)

        # Optional: systemd journal / syslog handler
        if log_to_journal:
            if _HAS_JOURNAL and JournalHandler is not None:
                j_ident = journal_identifier or logger_name
                try:
                    journal_handler = JournalHandler(SYSLOG_IDENTIFIER=j_ident)
                    journal_handler.setFormatter(plain_formatter)
                    logger.addHandler(journal_handler)
                except Exception:
                    # Fall back to SysLogHandler below
                    pass
            # If no systemd.journal or it failed: fall back to syslog
            if not any(isinstance(h, SysLogHandler) for h in logger.handlers) and not (
                _HAS_JOURNAL
                and any(
                    h.__class__.__name__ == "JournalHandler" for h in logger.handlers
                )
            ):
                try:
                    syslog_handler = SysLogHandler(address="/dev/log")
                except Exception:
                    # Fallback for systems without /dev/log (e.g., some containers)
                    syslog_handler = SysLogHandler(address=("localhost", 514))
                syslog_handler.setFormatter(plain_formatter)
                logger.addHandler(syslog_handler)

        # Prevent log messages from being propagated to higher level loggers
        logger.propagate = False
