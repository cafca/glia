"""
Alembic supplementary upgrade using ORM

"""
from uuid import uuid4

from glia import create_app
from nucleus.nucleus.database import db
from nucleus.nucleus.vesicle import Vesicle
from nucleus.nucleus.models import Identity, Starmap


def upgrade(logger):
    identities = Identity.query.all()
    logger.info("Creating Mindspaces")
    for identity in identities:
        if identity.mindspace is not None:
            if identity.mindspace.kind.endswith("_profile"):
                new_kind = "{}_mspace".format(identity.kind)
                app.logger.info("Updating {} mindspace kind to `{}`".format(
                    identity, new_kind))
                identity.mindspace.kind = new_kind

        if identity.profile is None:
            logger.info("Creating profile for {}".format(identity))
            profile = Starmap(
                id=uuid4().hex,
                author=identity,
                kind="{}_profile".format(identity.kind),
                modified=identity.created)
            identity.profile = profile
        db.session.add(identity)

    db.session.commit()

if __name__ == "__main__":
    app = create_app()
    app.logger.info("Starting upgrade")
    with app.test_request_context('/'):
        upgrade(app.logger)
    app.logger.info("Upgrade successful")
