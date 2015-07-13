"""
Alembic supplementary upgrade using ORM

"""
import sys, os
sys.path.append(os.getcwd())

from uuid import uuid4

from glia import create_app
from nucleus.nucleus.database import db
from nucleus.nucleus.vesicle import Vesicle
from nucleus.nucleus.models import MovementMemberAssociation, Persona


def upgrade(logger):
    personas = Persona.query.all()

    for p in personas:
        app.logger.info("Checking {}".format(p))
        assocs = MovementMemberAssociation.query \
            .filter_by(persona=p) \
            .order_by(MovementMemberAssociation.created.desc())
        def pm(mma):
            return " ".join([str(mma.persona), str(mma.movement), str(mma.created)])
        print pm(assocs[0]), "[keep]"
        print "\n".join(map(pm, assocs[1:]))
        for mma in assocs[1:]:
            db.session.delete(mma)
    db.session.commit()



if __name__ == "__main__":
    app = create_app()
    app.logger.info("Starting upgrade")
    with app.test_request_context('/'):
        upgrade(app.logger)
    app.logger.info("Upgrade finished")
