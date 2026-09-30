# Modelo de domínio inicial — Etapa 2

Este modelo é uma base técnica inicial, não uma validação das regras administrativas do MGI/ES. As tabelas começam vazias. Não há seed de órgãos, faturas, processos ou alertas.

## Entidades

- **organizations**, **services**: catálogos sem valores institucionais pré-carregados.
- **source_documents**: referência lógica por chave de fonte + caminho relativo + SHA-256; não guarda path absoluto e não modifica documentos.
- **extraction_candidates**: valores candidatos com método, localização da evidência, confiança opcional e estado de revisão. Não armazena trechos do documento nesta versão.
- **invoices**: metadados confirmados ou em revisão; `review_state` e `payment_state` são dimensões separadas. O estado `paid` só poderá ser atribuído por operação autorizada com evidência, ainda não implementada.
- **sei_processes**: número armazenado localmente com `verification_state=unverified` por padrão; não é consulta ao SEI.
- **invoice_process_links**, **invoice_document_links**: vínculos N:N com origem/estado explícitos.
- **alerts**: chave de deduplicação e ciclo de vida, sem regras de geração ativa.
- **audit_events**: estrutura de eventos append-oriented; ainda não possui ator autenticado, escrita automática ou proteção imutável.

## Estados técnicos iniciais

- Documento: `discovered`, `queued`, `processing`, `review`, `complete`, `error`, `ignored`.
- Revisão da fatura: `pending_review`, `confirmed`, `rejected`, `archived`.
- Pagamento: `unknown`, `unpaid`, `paid`, `cancelled`.
- Validação SEI: `unverified`, `verified`, `invalid`, `unavailable`.
- Vínculo fatura-processo: `suggested`, `confirmed`, `rejected`.
- Alerta: `new`, `acknowledged`, `resolved`, `dismissed`.

Os estados são rótulos técnicos provisórios; alinhar transições e semântica com os responsáveis antes de uso operacional.

## API adicionada

- `GET /api/v1/invoices?limit=&offset=&review_state=`
- `GET /api/v1/processes?limit=&offset=`
- `GET /api/v1/alerts?limit=&offset=&status=`

As rotas apenas leem registros persistidos e retornam listas vazias quando não existem dados. Não há rotas de escrita nem autenticação ainda; portanto, a API deve permanecer em ambiente local de desenvolvimento e não ser publicada em rede.

## Migrações e banco local

- SQLAlchemy 2 e Alembic.
- Banco padrão de desenvolvimento/testes: SQLite local (`sig_es_dev.db`), ignorado pelo Git.
- PostgreSQL local foi informado pelo usuário como instalado; o serviço Windows `postgresql-x64-18` foi observado como `Running` nesta máquina.
- Driver Psycopg 3 foi incluído e `SIGES_DATABASE_URL` aceita `postgresql+psycopg://`.
- A conectividade PostgreSQL ainda não foi validada: `psql` não está no PATH e faltam URL, banco, usuário e permissões. Não foram tentadas credenciais padrão nem mudanças no servidor.
- Não utilizar `create_all` em produção; aplicar migrações aprovadas.
- A migração inicial usa o metadata ORM para criar/drop schema e requer revisão antes de produção.
