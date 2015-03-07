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
