import re
import sendgrid
import os

from nucleus.nucleus.models import Group
from flask import render_template
from uuid import uuid4


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


def send_validation_email(user, db):
    """Send validation email using sendgrid, resetting the signup code.

    Args:
        user (User): Nucleus user object
        db (SQLAlchemy): Database used to store user's new signup code

    """
    from .. import db

    sg_user = os.environ.get('SENDGRID_USERNAME')
    sg_pass = os.environ.get('SENDGRID_PASSWORD')
    sg = sendgrid.SendGridClient(sg_user, sg_pass)

    user.signup_code = uuid4().hex
    db.session.add(user)
    db.session.commit()

    name = user.active_persona.username
    email = user.email

    if name is None or email is None:
        raise ValueError("Username and email can't be empty")

    message = sendgrid.Mail()
    message.add_to("{} <{}>".format(name, email))
    message.set_subject('Please confirm your email address')
    message.set_text(render_template("email/signup_confirmation.html", user=user))
    message.set_from('RKTIK Email Confirmation')
    status, msg = sg.send(message)
