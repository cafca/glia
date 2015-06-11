import logging

from urlparse import urlparse, urljoin
from flask import request, url_for, redirect
from flask.ext.login import current_user
from flask_wtf import Form
from wtforms import TextField, TextAreaField, HiddenField, PasswordField, validators

from nucleus.nucleus import ALLOWED_COLORS
from nucleus.nucleus.models import User, Star, Persona

logger = logging.getLogger('web')


def is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and \
        ref_url.netloc == test_url.netloc


def get_redirect_target():
    for target in request.args.get('next'), request.referrer:
        if not target:
            continue
        if is_safe_url(target):
            return target


class DeleteStarForm(Form):
    star_id = HiddenField()


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
            return False

        if not user.check_password(self.password.data):
            self.password.errors.append("Wrong password.")

        self.user = user
        return True


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


class CreatePersonaForm(Form):
    username = SignupForm.username
    password = SignupForm.password
    color = SignupForm.color
    movement = HiddenField()

    def validate(self):
        rv = Form.validate(self)
        if not rv:
            return False

        if current_user.check_password(self.password.data) is False:
            self.password.errors.append("Your password was not correct. Try again?")
            rv = False

        if current_user.associations.join(Persona).filter(Persona.username == self.username.data).count() > 0:
            self.username.errors.append("You already have a Persona going by that username")
            rv = False

        return rv


class CreateMovementForm(Form):
    id = HiddenField()
    name = TextField('Choose a name for your Movement *', [validators.Required(), validators.Length(min=3, max=20)])
    mission = TextField('Describe your mission', [validators.Length(max=140)])


class CreateStarForm(Form):
    parent = HiddenField()
    starmap = HiddenField()
    text = TextField('Enter text', [validators.Required(), validators.Length(min=1, max=140)])
    longform = TextAreaField('Add more detail')
    lfsource = TextField('Source of longform (eg. website URL)', [validators.Length(max=128)])

    def validate(self):
        rv = Form.validate(self)
        if rv and self.parent.data:
            parent = Star.query.get(self.parent.data)
            if parent is None:
                rv = False
                logger.warning("Create Star form failed because parent '{}' could not \
                    be found.".format(self.parent.data))
                self.parent.errors.append("Can't find the post you are \
                    replying to. Please try reloading the page.")
        return rv


class CreateReplyForm(CreateStarForm):
    def validate(self):
        rv = CreateStarForm.validate(self)
        if rv and self.parent.data is None:
            logger.warning("Reply form failed because no parent id was given")
            self.parent.errors.append("Can't find the post you are \
                replying to. Please try reloading the page.")
        return rv
