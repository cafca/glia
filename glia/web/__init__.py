import logging

from flask import Blueprint
from flask.ext.login import current_user

from nucleus.nucleus.models import Starmap, Movement, MovementMemberAssociation as Mma

app = Blueprint('web', __name__)
app.logger = logging.getLogger('web')


@app.context_processor
def inject_repost_starmaps():
    rv = []
    if not current_user.is_anonymous():
        rv.append(current_user.active_persona.mindspace)
        rv.append(current_user.active_persona.blog)

        # Is a movement member
        rv = rv + Starmap.query.join(Movement, Movement.mindspace_id == Starmap.id).join(Mma).filter(Mma.persona == current_user.active_persona).all()

        # Followed movements
        # rv = rv + [m.mindspace for m in current_user.active_persona.movements_followed]

        print [m.name for m in rv if m is not None]

    return dict(
        repost_starmaps=rv
    )

import views
import events
import async
