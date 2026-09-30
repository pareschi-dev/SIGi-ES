"""Classify numeric candidates independently from gross/net basis."""

from alembic import op
import sqlalchemy as sa

revision = "0004_candidate_amount_role"
down_revision = "0003_admin_rule_drafts"
branch_labels = None
depends_on = None

ROLE_CHECK = (
    "amount_role IS NULL OR amount_role IN "
    "('unspecified','total_amount','installment_amount','percentage','interest','penalty',"
    "'fine','discount','tax','fee','unit_price','quantity','other_numeric')"
)


def upgrade() -> None:
    """Add the optional semantic amount role without changing existing candidates."""
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("extraction_candidates")}
    checks = {check["name"] for check in inspector.get_check_constraints("extraction_candidates")}
    has_role = "amount_role" in columns
    has_check = "ck_candidate_amount_role" in checks

    if has_role and has_check:
        return
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("extraction_candidates", recreate="always") as batch_op:
            if not has_role:
                batch_op.add_column(sa.Column("amount_role", sa.String(length=24), nullable=True))
            if not has_check:
                batch_op.create_check_constraint("ck_candidate_amount_role", ROLE_CHECK)
        return

    if not has_role:
        op.add_column("extraction_candidates", sa.Column("amount_role", sa.String(length=24), nullable=True))
    if not has_check:
        op.create_check_constraint("ck_candidate_amount_role", "extraction_candidates", ROLE_CHECK)


def downgrade() -> None:
    """Remove the classification column from disposable development databases."""
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("extraction_candidates")}
    checks = {check["name"] for check in inspector.get_check_constraints("extraction_candidates")}
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("extraction_candidates", recreate="always") as batch_op:
            if "ck_candidate_amount_role" in checks:
                batch_op.drop_constraint("ck_candidate_amount_role", type_="check")
            if "amount_role" in columns:
                batch_op.drop_column("amount_role")
        return
    if "ck_candidate_amount_role" in checks:
        op.drop_constraint("ck_candidate_amount_role", "extraction_candidates", type_="check")
    if "amount_role" in columns:
        op.drop_column("extraction_candidates", "amount_role")
