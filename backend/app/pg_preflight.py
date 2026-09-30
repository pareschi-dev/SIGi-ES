"""Read-only PostgreSQL connectivity and schema preflight for local setup."""

from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from app.db import engine

EXPECTED_SIGES_TABLES = {
    "alembic_version",
    "organizations",
    "services",
    "source_documents",
    "sei_processes",
    "invoices",
    "invoice_process_links",
    "invoice_document_links",
    "extraction_candidates",
    "alerts",
    "audit_events",
    "administrative_rule_drafts",
}


def main() -> int:
    """Print server identity and fail if the target public schema is non-empty."""
    try:
        with engine.connect() as connection:
            identity = connection.execute(
                text("SELECT current_database(), current_user, current_schema(), version()")
            ).one()
            tables = set(inspect(connection).get_table_names(schema="public"))
    except SQLAlchemyError as exc:
        original = exc.orig
        sqlstate = getattr(original, "sqlstate", None)
        diagnostics = getattr(original, "diag", None)
        primary_message = getattr(diagnostics, "message_primary", None)
        if sqlstate:
            print(f"Conexão PostgreSQL recusada pelo servidor (SQLSTATE {sqlstate}).")
        else:
            print(f"Falha de conexão PostgreSQL ({type(original).__name__}); verifique host e porta.")
        if primary_message:
            print(f"Detalhe informado pelo servidor: {primary_message}")
        print("Nenhuma migração foi iniciada. A senha e a URL de conexão não serão exibidas.")
        return 1

    database, user, schema, version = identity
    print(f"Conectado: banco={database}; usuário={user}; schema={schema}")
    print(f"Servidor: {version.splitlines()[0]}")
    if tables and not (
        "alembic_version" in tables and tables.issubset(EXPECTED_SIGES_TABLES)
    ):
        print("Migração interrompida: schema public já contém tabelas:")
        for table in tables:
            print(f"- {table}")
        print("Revise o conteúdo e a propriedade deste banco antes de migrar.")
        return 2
    if tables:
        print("Schema public contém somente tabelas SIG-ES esperadas; Alembic pode avançar migrações.")
    else:
        print("Schema public vazio; seguro para avaliar a migração inicial.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
