import logging
import sys

from colorlog import ColoredFormatter
from flask import Request, session

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


class AnonymousPersona(object):
    """Used by Flask-Login"""

    class active_persona():
        username = "Anonymous"

    def get_id(self):
        return None

    def is_active(self):
        return False

    def is_authenticated(self):
        return False

    def is_anonymous(self):
        return False


class ProxiedRequest(Request):
    """
    `Request` subclass that overrides `remote_addr` with Frontend Server's
    HTTP_X_FORWARDED_FOR when available.
    """

    @property
    def remote_addr(self):
        """The remote address of the client."""
        # Get a parsed version of X-Forwarded-For header (contains
        #    REMOTE_ADDR if no forwarded-for header). See
        #    http://en.wikipedia.org/wiki/X-Forwarded-For
        fwd = self.access_route
        remote = self.environ.get('REMOTE_ADDR', None)
        if fwd and self._is_private_ip(remote):
            # access route is a list where the client is first
            # followed by any intermediary proxies. However, we
            # can only trust the last entry as valid -- it's from
            # the server one hop behind the one connecting.
            return fwd[-1]
        else:
            return remote

    def _is_private_ip(self, ip):
        blank_ip = (ip is None or ip == '')
        private_ip = (ip.startswith('10.') or ip.startswith('172.16.') or ip.startswith('192.168.'))
        local_ip = (ip == '127.0.0.1' or ip == '0.0.0.0')
        return blank_ip or private_ip or local_ip

# --- use this class so we get real IPs
# from real_ip_address import ProxiedRequest
# app = [...]
# app.request_class = ProxiedRequest


def get_active_persona():
    """ Return the currently active persona or 0 if there is no controlled persona. """
    from nucleus.nucleus.models import Persona
    return Persona.query.get(session['active_persona'])
