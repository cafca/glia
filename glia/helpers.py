import logging
import sys

from colorlog import ColoredFormatter
from flask import Request, session
from jinja2 import Environment, PackageLoader, Markup, evalcontextfilter

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
        id = None
        username = "New User"

    def get_id(self):
        return None

    def is_active(self):
        return False

    def is_authenticated(self):
        return False

    def is_anonymous(self):
        return True


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


@evalcontextfilter
def inject_mentions(eval_ctx, text, thought, nolink=False):
    """Replace portions of Thought text with a link to the mentioned Identity for
    every mention registered on the Thought"""

    from flask import url_for
    env = Environment(loader=PackageLoader('glia', 'templates'))
    env.globals['url_for'] = url_for
    template = env.get_template('macros/identity.html')
    mentions = [pa.percept for pa in thought.percept_assocs.all() if pa.percept.kind == "mention"]

    for mention in mentions:
        if mention.identity.kind == "persona":
            rendered_link = template.module.persona(mention.identity, nolink=nolink)
        else:
            rendered_link = template.module.movement(mention.identity, nolink=nolink)

        if eval_ctx.autoescape:
            rendered_link = Markup(rendered_link)
        text = text.replace("".join(["@", mention.text]), rendered_link)

    if eval_ctx.autoescape:
        text = Markup(text)

    return text


def gallery_col_width(pa_list):
    """Return the right column width for displaying a number of images"""
    if len(pa_list) <= 4:
        rv = 12 / len(pa_list)
    else:
        rv = 4
    return rv


def sort_hot(query):
    """Sort thoughts by their hotness"""
    from nucleus.nucleus.models import Thought
    return sorted(query, key=Thought.hot, reverse=True)
