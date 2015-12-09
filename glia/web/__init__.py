import logging

from flask import Blueprint
from flask.ext.login import current_user

from forms import LoginForm

from nucleus.nucleus.identity import Movement
from nucleus.nucleus.context import Mindset

app = Blueprint('web', __name__)
app.logger = logging.getLogger('web')

VIEW_CACHE_TIMEOUT = 5


@app.context_processor
def inject_repost_mindsets():
    rv = []
    if not current_user.is_anonymous():
        rv = Mindset.query.filter(Mindset.id.in_(
            current_user.active_persona.repost_mindsets()))

    return dict(
        repost_mindsets=rv
    )


@app.context_processor
def inject_login_form():
    return {"global_login_form": LoginForm() if current_user.is_anonymous() else None}


@app.context_processor
def inject_navbar_movements():
    if current_user.is_anonymous():
        movements = Movement.top_movements()
    else:
        movements = current_user.active_persona.movements()

    return dict(nav_movements=movements)

import views
import events
import async
