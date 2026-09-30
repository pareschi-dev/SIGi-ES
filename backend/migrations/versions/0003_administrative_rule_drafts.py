"""Add versioned administrative-rule drafts."""

from alembic import op
import sqlalchemy as sa

revision = "0003_admin_rule_drafts"
down_revision = "0002_amount_basis"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create draft storage if it is not already present on fresh metadata installs."""
    inspector = sa.inspect(op.get_bind())
    if "administrative_rule_drafts" in inspector.get_table_names():
        return
    op.create_table(
        "administrative_rule_drafts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope_type", sa.String(length=16), nullable=False),
        sa.Column("scope_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("rule_data", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("scope_type IN ('supplier','material')", name="ck_admin_rule_scope_type"),
        sa.CheckConstraint("scope_id > 0", name="ck_admin_rule_positive_scope_id"),
        sa.CheckConstraint("version > 0", name="ck_admin_rule_positive_version"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scope_type", "scope_id", name="uq_admin_rule_scope"),
    )
    op.create_index(
        "ix_admin_rule_scope",
        "administrative_rule_drafts",
        ["scope_type", "scope_id"],
    )


def downgrade() -> None:
    """Remove draft-rule storage; keep the audit log intact."""
    inspector = sa.inspect(op.get_bind())
    if "administrative_rule_drafts" not in inspector.get_table_names():
        return
    op.drop_index("ix_admin_rule_scope", table_name="administrative_rule_drafts")
    op.drop_table("administrative_rule_drafts")
