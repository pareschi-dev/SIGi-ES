"""Track invoice-document quarantine and release workflow."""

from alembic import op
import sqlalchemy as sa

revision = "0005_invoice_quarantine_workflow"
down_revision = "0004_candidate_amount_role"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Place existing documents in quarantine without changing source files."""
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("source_documents")}
    checks = {check["name"] for check in inspector.get_check_constraints("source_documents")}
    has_state = "invoice_workflow_state" in columns
    has_check = "ck_document_invoice_workflow_state" in checks

    if has_state and has_check:
        return
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("source_documents", recreate="always") as batch_op:
            if not has_state:
                batch_op.add_column(
                    sa.Column(
                        "invoice_workflow_state",
                        sa.String(length=16),
                        nullable=False,
                        server_default="quarantined",
                    )
                )
            if not has_check:
                batch_op.create_check_constraint(
                    "ck_document_invoice_workflow_state",
                    "invoice_workflow_state IN ('quarantined','invoices')",
                )
        return

    if not has_state:
        op.add_column(
            "source_documents",
            sa.Column(
                "invoice_workflow_state",
                sa.String(length=16),
                nullable=False,
                server_default="quarantined",
            ),
        )
    if not has_check:
        op.create_check_constraint(
            "ck_document_invoice_workflow_state",
            "source_documents",
            "invoice_workflow_state IN ('quarantined','invoices')",
        )
    op.alter_column("source_documents", "invoice_workflow_state", server_default=None)


def downgrade() -> None:
    """Remove workflow metadata while preserving document and candidate rows."""
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("source_documents")}
    checks = {check["name"] for check in inspector.get_check_constraints("source_documents")}
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("source_documents", recreate="always") as batch_op:
            if "ck_document_invoice_workflow_state" in checks:
                batch_op.drop_constraint("ck_document_invoice_workflow_state", type_="check")
            if "invoice_workflow_state" in columns:
                batch_op.drop_column("invoice_workflow_state")
        return
    if "ck_document_invoice_workflow_state" in checks:
        op.drop_constraint("ck_document_invoice_workflow_state", "source_documents", type_="check")
    if "invoice_workflow_state" in columns:
        op.drop_column("source_documents", "invoice_workflow_state")
