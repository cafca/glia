import logging

from flask import Blueprint

from nucleus.nucleus.models import Starmap, Persona

app = Blueprint('web', __name__)
app.logger = logging.getLogger('web')


@app.context_processor
def inject_repost_starmaps():
    return dict(
        repost_starmaps=Starmap.query.group_by(Starmap.kind, Starmap.id)
    )

import views
import events
import async
