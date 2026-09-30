"""Initial SIG-ES domain tables for development and integration testing."""

from alembic import op

from app.models import Base

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the initial relational schema from the checked-in metadata."""
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    """Drop the initial schema; use only in disposable environments."""
    Base.metadata.drop_all(bind=op.get_bind())
