import logging
import sys


def setup_loggers(loggers, log_format):
    """Setup loggers
    Flask is configured to route logging events only to the console if it is in debug
    mode. This overrides this setting and enables a new logging handler which prints
    to the shell."""

    console_handler = logging.StreamHandler(stream=sys.stdout)
    console_handler.setFormatter(logging.Formatter(log_format))

    for l in loggers:
        del l.handlers[:]  # remove old handlers
        l.setLevel(logging.DEBUG)
        l.addHandler(console_handler)
        l.propagate = False  # setting this to true triggers the root logger
