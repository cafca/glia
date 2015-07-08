import logging

from flask import Blueprint
from flask.ext.login import current_user
from sqlalchemy import func

from forms import LoginForm

from nucleus.nucleus.models import Mindset, Movement, MovementMemberAssociation as Mma

app = Blueprint('web', __name__)
app.logger = logging.getLogger('web')


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
        movements = Movement.query \
            .join(Mma) \
            .order_by(func.count(Mma.persona_id)) \
            .group_by(Mma.persona_id) \
            .group_by(Movement) \
            .limit(7)
    else:
        movements = Movement.query \
            .join(Mma) \
            .filter_by(persona=current_user.active_persona)

    return dict(nav_movements=movements)

import views
import events
import async
