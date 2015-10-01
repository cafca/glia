"""
Alembic supplementary upgrade using ORM

"""
import sys, os
sys.path.append(os.getcwd())

from glia import create_app
from nucleus.nucleus.database import db
from nucleus.nucleus.models import Thought


def upgrade(logger):
    thoughts = Thought.query.filter_by(kind="thought").filter(Thought._comment_count == None)
    for t in thoughts:
        logger.info("Updated {} to comment count {}".format(t, t.comment_count()))
        db.session.add(t)
    db.session.commit()


if __name__ == "__main__":
    app = create_app()
    app.logger.info("Starting upgrade")
    with app.test_request_context('/'):
        upgrade(app.logger)
    app.logger.info("Upgrade finished")
