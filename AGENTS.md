# AGENTS.md - Diretrizes para Agentes de IA

## 1. Visão Geral do Projeto
- **Nome:** SIG-ES (Sistema Inteligente de Gestão do Espírito Santo)
- **Propósito:** Aplicação local para monitoramento de arquivos (C:\2026), ingestão de dados e gestão de saldos.
- **Status:** Desenvolvimento local. NÃO está homologado para produção.
- **Ambiente:** Windows, PowerShell, Loopback (127.0.0.1).

## 2. Stack Tecnológica
- **Backend:** Python 3.10+, FastAPI, SQLAlchemy, Alembic (migrações), PostgreSQL (SIG-SAMF).
- **Frontend:** Node.js 20+, Vite, TypeScript.
- **Automação:** PowerShell (scripts .ps1).
- **Testes:** Pytest (backend), npm build (frontend).

## 3. Estrutura de Pastas Principal
- `backend/`: API FastAPI, modelos, migrações e scripts de inicialização.
- `frontend/`: Interface Vite/TypeScript.
- `docs/`: Documentação de regras de negócio e arquitetura.
- `iniciar-siges.ps1`: Script mestre para iniciar tudo (API + Frontend + Monitor).
- `SIG-ES.txt`: Documento de requisitos e contexto.

## 4. Comandos Essenciais
- **Iniciar Sistema Completo:** `cd frontend; npm run dev`
- **Iniciar Apenas API Local:** `backend/run-local.ps1` (ou `.\iniciar-siges.ps1`)
- **Rodar Testes Backend:** `cd backend; ..\.venv\Scripts\python.exe -m pytest`
- **Build Frontend:** `cd frontend; npm run build`
- **Migrações DB:** `..\.venv\Scripts\python.exe -m alembic upgrade head`

## 5. Regras de Segurança e Limites (CRÍTICO - NUNCA QUEBRAR)
- **NUNCA** exponha a API na rede. Ela deve permanecer em `127.0.0.1`.
- **NUNCA** coloque senhas no código, em logs ou no chat. O script solicita a senha oculta no terminal.
- **NUNCA** mova, renomeie, apague ou edite os arquivos originais da pasta `C:\2026`. O monitor apenas lê metadados e calcula hash.
- **NUNCA** assuma que o sistema consulta o SEI, confirma pagamentos ou determina saldos oficiais. Isso é proibido.
- **SEMPRE** valide se as portas 8000 e 5173 estão livres antes de iniciar.
- O monitoramento só observa eventos *após* a inicialização. Cargas históricas exigem processo separado.

## 6. Padrões de Código
- **Python:** Siga a PEP8. Use Type Hints. Mantenha a lógica de negócio separada das rotas da API.
- **TypeScript/React:** Use componentes funcionais e hooks. Mantenha a tipagem estrita.
- **Documentação:** Qualquer nova funcionalidade deve ser documentada na pasta `docs/`.
- **Commits:** Use mensagens claras e descritivas em português.

## 7. Próximos Passos / Pendências
- (Deixe esta seção para a IA ou para você ir atualizando conforme o desenvolvimento avança).