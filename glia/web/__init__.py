import logging

from flask import Blueprint

app = Blueprint('web', __name__)
app.logger = logging.getLogger('web')

import views
import events
import async
