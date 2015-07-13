"""
Alembic supplementary upgrade using ORM

"""
import sys, os
sys.path.append(os.getcwd())

from uuid import uuid4

from glia import create_app
from nucleus.nucleus.database import db
from nucleus.nucleus.models import MovementMemberAssociation, Movement, Persona


def upgrade(logger):
    personas = Persona.query.all()

    for p in personas:
        app.logger.info("Checking {}".format(p))
        movements = Movement.query \
            .join(MovementMemberAssociation) \
            .filter(MovementMemberAssociation.persona == p)

        for m in movements:
            assocs = MovementMemberAssociation.query.filter_by(movement=m).filter_by(persona=p).order_by(MovementMemberAssociation.created.desc())
            print "\tMember of", m.username, assocs.count(), "assocs"
            for assoc in assocs[1:]:
                print "\tdelete", assoc
                db.session.delete(assoc)

    db.session.commit()


if __name__ == "__main__":
    app = create_app()
    app.logger.info("Starting upgrade")
    with app.test_request_context('/'):
        upgrade(app.logger)
    app.logger.info("Upgrade finished")
