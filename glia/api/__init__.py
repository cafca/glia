import logging
from flask import Blueprint

app = Blueprint('api', __name__)
app.logger = logging.getLogger('api')

import views
import myelin
