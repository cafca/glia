import logging

from flask import Blueprint
from flask.ext.login import current_user

from forms import LoginForm

from nucleus.nucleus.models import Mindset, Movement, MovementMemberAssociation as Mma

app = Blueprint('web', __name__)
app.logger = logging.getLogger('web')

VIEW_CACHE_TIMEOUT = 50


@app.context_processor
def inject_repost_mindsets():
    rv = []
    if not current_user.is_anonymous():
        rv.append(current_user.active_persona.mindspace)
        rv.append(current_user.active_persona.blog)

        # Is a movement member
        rv = rv + Mindset.query.join(Movement, Movement.mindspace_id == Mindset.id).join(Mma).filter(Mma.persona == current_user.active_persona).all()

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
        user_movements = Movement.query \
            .join(Mma) \
            .filter_by(persona=current_user.active_persona)

        movements = [dict(id=m.id, username=m.username)
            for m in user_movements]

    return dict(nav_movements=movements)

import views
import events
import async
