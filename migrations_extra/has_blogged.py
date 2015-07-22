"""
Alembic supplementary upgrade using ORM

"""
import sys, os
sys.path.append(os.getcwd())

from glia import create_app
from nucleus.nucleus.database import db
from nucleus.nucleus.models import Movement


def upgrade(logger):
    movements = Movement.query.all()
    for m in movements:
        for t in m.blog.index:
            if t.parent:
                t.parent._blogged = True
                logger.info("{} was blogged by {}".format(t.parent, m))
                db.session.add(t.parent)
            else:
                logger.info("{} has no parent".format(t))

    db.session.commit()


if __name__ == "__main__":
    app = create_app()
    app.logger.info("Starting upgrade")
    with app.test_request_context('/'):
        upgrade(app.logger)
    app.logger.info("Upgrade finished")
