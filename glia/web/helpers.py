import logging
import os
import pytz
import re
import sendgrid

from flask import render_template
from flask.ext.login import login_user
from goose import Goose
from uuid import uuid4
from sendgrid import SendGridClient, SendGridClientError, SendGridServerError
from sqlalchemy import inspect

from nucleus.nucleus.models import Group, LinkPlanet, LinkedPicturePlanet, TextPlanet

logger = logging.getLogger('web')


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


def send_email(message):
    """Send Email using Sendgrid service

    Args:
        message (Sendgrid Message): Readily configured message object

    Raises:
        SendGridClientError
        SendGridServerError
    """
    from flask import current_app

    sg_user = os.environ.get('SENDGRID_USERNAME') or current_app.config["SENDGRID_USERNAME"]
    sg_pass = os.environ.get('SENDGRID_PASSWORD') or current_app.config["SENDGRID_PASSWORD"]
    sg = SendGridClient(sg_user, sg_pass, raise_errors=True)
    return sg.send(message)


def send_validation_email(user, db):
    """Send validation email using sendgrid, resetting the signup code.

    Args:
        user (User): Nucleus user object
        db (SQLAlchemy): Database used to store user's new signup code

    Throws:
        ValueError: If active user has no name or email address
    """
    from .. import db
    from flask import current_app

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
    message.set_html(render_template("email/signup_confirmation.html", user=user))
    message.set_from('RKTIK Email Confirmation')

    # Override activation step if email can't be sent in dev environment
    def activate_user():
        logger.warning("User is being auto-activated in dev environment")
        login_user(user, remember=False)
        user.active = True
        db.session.add(user)
        db.session.commit()

    try:
        status, msg = send_email(message)
    except SendGridClientError, e:
        logger.error("Client error sending confirmation email: {}".format(e))
        if current_app.config.get('DEBUG') is True:
            activate_user()
    except SendGridServerError, e:
        logger.error("Server error sending confirmation email: {}".format(e))
        if current_app.config.get('DEBUG') is True:
            activate_user()


def find_links(text):
    """Given a text, find all alive links inside

    Args:
        text(String): The input to parse

    Returns:
        tuple:
            list: List of response objects for found URLs
            str: Text with links removed if they occur at the end
    """
    import re
    import requests

    # Everything that looks remotely like a URL
    expr = "((?:https?://)?\S+\.\w{2,3}\S*)"
    rv = list()

    candidates = re.findall(expr, text)

    if candidates:
        for i, c in enumerate(candidates[::-1]):
            if c[:4] != "http":
                c_schemed = "".join(["http://", c])
            else:
                c_schemed = c

            logger.info("Testing potential link '{}' for availability".format(c_schemed))
            try:
                res = requests.head(c_schemed, timeout=3.0)
            except (requests.exceptions.RequestException, ValueError):
                # The link failed
                pass
            else:
                if res and res.status_code < 400:
                    rv.append(res)
                    # Only remove link if it occurs at the end of text
                    if (text.index(c) + len(c)) == len(text.rstrip()):
                        text = text.replace(c, "")
    return (rv, text)


def process_attachments(text):
    """Given some text a user entered, extract all attachments
    hinted at and return user message plus a list of Planet objects

    Args:
        text (String): Message entered by user

    Return:
        Tuple
            0: Message with some attachment hints removed (URLs)
            1: List of Planet instances extracted from text
    """
    g = Goose()
    planets = list()

    links, text = find_links(text)
    for link in links:
        linkplanet = LinkPlanet.get_or_create(link.url)
        planets.append(linkplanet)

        if not isinstance(linkplanet, LinkedPicturePlanet):
            page = g.extract(url=link.url)

            # Add metadata if planet object is newly created
            if inspect(linkplanet).transient is True:
                linkplanet.title = page.title

            # Extract article contents as new Planet
            if len(page.cleaned_text) > 300:
                textplanet = TextPlanet.get_or_create(page.cleaned_text)
                textplanet.source = link.url

                planets.append(textplanet)

    return (text, planets)


def localtime(value, tzval="UTC"):
    """Convert tz-naive UTC datetime into tz-naive local datetime

    Args:
        value (datetime): timezone naive UTC datetime
        tz (sting): timezone e.g. 'Europe/Berlin' (see pytz references)
    """
    value = value.replace(tzinfo=pytz.utc)  # assuming value is utc time
    value = value.astimezone(pytz.timezone(tzval))  # convert to local time (tz-aware)
    value = value.replace(tzinfo=None)  # make tz-naive again
    return value
