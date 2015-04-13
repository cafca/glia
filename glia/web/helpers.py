import re

from nucleus.nucleus.models import Group


class UnauthorizedError(Exception):
    """Current user is not authorized for this action"""
    pass


def get_group_from_path(path):
    """Return a group for a given URL or None

    Args:
        path (String): /group/<id> with id beign 32 bytes
    """
    rx = "^/groups/(.{32})"
    rx_match = re.match(rx, path)
    if rx_match:
        group_id = rx_match.group(1)
        return Group.query.get(group_id)


def find_links(text, logger):
    """Given a text, find all alive links inside

    Args:
        text(String): The input to parse

    Returns:
        tuple:
            list: List of response objects for found URLs
            str: Text with all link occurrences removed
    """
    import re
    import requests

    # Everything that looks remotely like a URL
    # expr = "(https?://[\S]+)"
    expr = "(.*\w+\.\w{2,3}/?.*)"
    rv = list()

    candidates = re.findall(expr, text)

    if candidates:
        for i, c in enumerate(candidates):
            if c[:4] != "http":
                c_scheme = "".join(["http://", c])
            else:
                c_scheme = c

            logger.info("Testing potential link '{}' for availability".format(c_scheme))
            try:
                res = requests.head(c_scheme, timeout=3.0)
            except (requests.exceptions.RequestException, ValueError):
                # The link failed
                pass
            else:
                if res and res.status_code < 400:
                    rv.append(res)
                    text = text.replace(c, "({})[{}]".format(c, res.url))
    return (rv, text)
