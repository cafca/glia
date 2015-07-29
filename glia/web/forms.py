import logging

from urlparse import urlparse, urljoin
from flask import request, url_for, redirect
from flask.ext.login import current_user
from flask_wtf import Form
from wtforms import TextField, TextAreaField, HiddenField, PasswordField, \
    validators, BooleanField, SelectMultipleField

from nucleus.nucleus import ALLOWED_COLORS
from nucleus.nucleus.models import User, Thought, Persona

logger = logging.getLogger('web')


def get_redirect_target():
    for target in request.args.get('next'), request.referrer:
        if not target:
            continue
        if is_safe_url(target):
            return target


def is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and \
        ref_url.netloc == test_url.netloc


class EmailPrefsForm(Form):
    email_react_private = BooleanField("When I receive a private message")
    email_react_reply = BooleanField("When someone replies to my thoughts")
    email_react_mention = BooleanField("When someone mentions me")
    email_react_follow = BooleanField("When someone follows me")
    email_system_security = BooleanField("Important security notices")
    email_system_features = BooleanField("When RKTIK gets a cool new feature")
    email_catchall = BooleanField("Don't send any emails at all. Emails are disgusting!")


class RedirectForm(Form):
    next = HiddenField()

    def __init__(self, *args, **kwargs):
        Form.__init__(self, *args, **kwargs)
        if not self.next.data:
            self.next.data = get_redirect_target() or ''

    def redirect(self, endpoint='index', **values):
        if is_safe_url(self.next.data):
            return redirect(self.next.data)
        target = get_redirect_target()
        return redirect(target or url_for(endpoint, **values))


class SignupForm(RedirectForm):
    email = TextField('Email', [validators.Required(), validators.Email(), validators.Length(max=128)])
    password = PasswordField('Password', [validators.Required(), validators.Length(min=8)])
    username = TextField('Username', [validators.Required(), validators.Regexp("\S{3,20}")])
    color = TextField('Color', [validators.Required(), validators.AnyOf(ALLOWED_COLORS.keys())])

    def validate(self):
        rv = Form.validate(self)
        if not rv:
            return False

        user = User.query.filter_by(email=self.email.data).first()
        if user:
            self.email.errors.append("A user with this email already exists. Please send an email to admin@rktik.com if someone else signed up with your address.")
            rv = False
        return rv


class CreateMovementForm(Form):
    id = HiddenField()
    name = TextField('Choose a name for your Movement *', [validators.Required(), validators.Length(min=3, max=20)])
    mission = TextField('Describe your mission', [validators.Length(max=140)])
    color = SignupForm.color
    private = BooleanField("Everything except for the blog is hidden")

    def validate(self):
        print self.color.data
        return Form.validate(self)


class CreatePersonaForm(Form):
    username = SignupForm.username
    password = SignupForm.password
    color = SignupForm.color
    movement = HiddenField()

    def validate(self):
        rv = Form.validate(self)

        if current_user.check_password(self.password.data) is False:
            self.password.errors.append("Your password was not correct. Try again?")
            rv = False

        if self.username.data in [p.username for p in current_user.associations]:
            self.username.errors.append("You already have a Persona going by that username")
            rv = False

        return rv


class CreateThoughtForm(Form):
    parent = HiddenField()
    mindset = HiddenField()
    text = TextField('Enter text', [validators.Required(), validators.Length(min=1, max=140)])
    longform = TextAreaField('Add more detail')
    lfsource = TextField('Source of longform (eg. website URL)', [validators.Length(max=128)])

    def validate(self):
        rv = Form.validate(self)
        if rv and self.parent.data:
            parent = Thought.query.get(self.parent.data)
            if parent is None:
                rv = False
                logger.warning("Create Thought form failed because parent '{}' could not \
                    be found.".format(self.parent.data))
                self.parent.errors.append("Can't find the post you are \
                    replying to. Please try reloading the page.")
        return rv


class EditThoughtForm(Form):
    text = TextField('Enter text', [validators.Required(), validators.Length(min=1, max=140)])
    longform = TextAreaField('Add more detail')
    lfsource = TextField('Source of longform (eg. website URL)', [validators.Length(max=128)])
    delete_attachments = SelectMultipleField("Delete attachments")

    def validate(self):
        rv = Form.validate(self)
        return rv


class CreateReplyForm(CreateThoughtForm):
    def validate(self):
        rv = CreateThoughtForm.validate(self)
        if rv and self.parent.data is None:
            logger.warning("Reply form failed because no parent id was given")
            self.parent.errors.append("Can't find the post you are \
                replying to. Please try reloading the page.")
        return rv


class DeleteThoughtForm(Form):
    thought_id = HiddenField()


class InviteMembersForm(Form):
    invites = TextAreaField(validators=[])
    message = TextField(validators=[])

    def validate(self):
        rv = Form.validate(self)
        if rv:
            self.handles = set()

            handles = self.invites.data.split("\n")
            for handle in handles:
                if "@" in handle and "." in handle:
                    self.handles.add(handle)
                elif len(handle) > 0:
                    self.invites.errors.append("{} does not seem to be a valid email address.".format(handle))
                    rv = False
            return rv


class LoginForm(RedirectForm):
    email = TextField('Email', [validators.Required(), validators.Email()])
    password = PasswordField('Password', [validators.Required()])

    def validate(self):
        """Validate user account"""

        rv = Form.validate(self)
        if not rv:
            return False

        user = User.query.filter_by(email=self.email.data).first()
        if user is None:
            self.email.errors.append("No user with that email is registered.")
            logger.warning("No user found for email '{}'".format(
                self.email.data))
            return False

        if not user.check_password(self.password.data):
            self.password.errors.append("Wrong password.")
            logger.warning("Invalid password for user {}".format(user))
            return False

        self.user = user
        return True
