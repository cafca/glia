from urlparse import urlparse, urljoin
from flask import request, url_for, redirect
from flask_wtf import Form
from wtforms import TextField, HiddenField, PasswordField, validators

from nucleus.nucleus.models import User


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

    def validate(self):
        rv = Form.validate(self)
        if not rv:
            return False

        user = User.query.filter_by(email=self.email.data).first()
        if user:
            self.email.errors.append("A user with this email address already exists.")
            rv = False

        return rv


class CreateGroupForm(Form):
    name = TextField('New group name', [validators.Required(), validators.Length(min=3, max=20)])
