"""Track whether a proposed monetary value is gross or net."""

from alembic import op
import sqlalchemy as sa

revision = "0002_amount_basis"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add an optional, explicitly reviewed monetary basis to candidates."""
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("extraction_candidates")}
    checks = {check["name"] for check in inspector.get_check_constraints("extraction_candidates")}
    has_basis = "amount_basis" in columns
    has_check = "ck_candidate_amount_basis" in checks

    if has_basis and has_check:
        return
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("extraction_candidates", recreate="always") as batch_op:
            if not has_basis:
                batch_op.add_column(sa.Column("amount_basis", sa.String(length=16), nullable=True))
            if not has_check:
                batch_op.create_check_constraint(
                    "ck_candidate_amount_basis",
                    "amount_basis IS NULL OR amount_basis IN ('gross','net','unspecified')",
                )
        return

    if not has_basis:
        op.add_column("extraction_candidates", sa.Column("amount_basis", sa.String(length=16), nullable=True))
    if not has_check:
        op.create_check_constraint(
            "ck_candidate_amount_basis",
            "extraction_candidates",
            "amount_basis IS NULL OR amount_basis IN ('gross','net','unspecified')",
        )


def downgrade() -> None:
    """Remove the candidate basis annotation."""
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("extraction_candidates")}
    checks = {check["name"] for check in inspector.get_check_constraints("extraction_candidates")}
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("extraction_candidates", recreate="always") as batch_op:
            if "ck_candidate_amount_basis" in checks:
                batch_op.drop_constraint("ck_candidate_amount_basis", type_="check")
            if "amount_basis" in columns:
                batch_op.drop_column("amount_basis")
        return
    if "ck_candidate_amount_basis" in checks:
        op.drop_constraint("ck_candidate_amount_basis", "extraction_candidates", type_="check")
    if "amount_basis" in columns:
        op.drop_column("extraction_candidates", "amount_basis")
