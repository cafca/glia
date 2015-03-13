import re
import sendgrid

from nucleus.nucleus.models import Group
from flask import render_template


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


def send_validation_email(user):
    """Send validation email using sendgrid

    Args:
        user (User): Nucleus user object

    """
    from .. import app

    sg = sendgrid.SendGridClient(app.config['SENDGRID_USERNAME'], app.config['SENDGRID_PASSWORD'])

    message = sendgrid.Mail()
    message.add_to("{} <{}>".format(user.active_persona.username, user.email))
    message.set_subject('Please confirm your email address')
    message.set_text(render_template("email/signup_confirmation.html", user=user))
    message.set_from('RKTIK Email Confirmation')
    status, msg = sg.send(message)
