import logging

from flask import Blueprint
from flask.ext.login import current_user

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

import views
import events
import async
