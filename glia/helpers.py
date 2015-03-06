import logging
import sys

from colorlog import ColoredFormatter

formatter = ColoredFormatter(
    "%(log_color)s%(name)s :: %(module)s [%(filename)s:%(lineno)d]%(reset)s %(message)s",
    datefmt=None,
    reset=True,
    log_colors={
        'DEBUG': 'cyan',
        'INFO': 'green',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'red,bg_white',
    },
    secondary_log_colors={},
    style='%'
)


def setup_loggers(loggers):
    """Setup loggers
    Flask is configured to route logging events only to the console if it is in debug
    mode. This overrides this setting and enables a new logging handler which prints
    to the shell."""

    console_handler = logging.StreamHandler(stream=sys.stdout)
    console_handler.setFormatter(formatter)

    for l in loggers:
        del l.handlers[:]  # remove old handlers
        l.setLevel(logging.DEBUG)
        l.addHandler(console_handler)
        l.propagate = False  # setting this to true triggers the root logger
