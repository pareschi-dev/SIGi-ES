# SIG-ES — Registro de implementação

> Registro cumulativo do que foi iniciado, implementado e validado. Atualizar este arquivo **no início de cada nova etapa** e novamente ao concluí-la. Informações de demonstração não representam dados oficiais.

## Estado atual
- Etapa ativa: **Etapa 34 — Revisão de pendências e liberação de faturas**
- Situação: iniciada; investigar por que faturas não avançam, permitir concluir os requisitos no formulário, destacar campos ausentes/ambíguos e selecionar referências do catálogo local não verificado.
- Atualizado em: 03/10/2026

### Etapa 35 — Sincronização do repositório e commit de implementação (em execução)
- [x] Registrar o estado desta etapa no arquivo de implementação antes de salvar o progresso no Git.
- [x] Confirmar o estado atual do repositório e preparar o commit com a mensagem solicitada.
- [ ] Realizar o commit final com a mensagem `implementação do sistema na SRA-ES` após revisão do status do Git.

### Etapa 34 — Revisão de pendências e liberação de faturas (iniciada)
- [x] Fechar lacunas do formulário que impedem concluir requisitos da liberação e permitir salvar alterações antes de tentar a transição.
- [x] Destacar campos vinculados a requisitos incompletos e refletir a resposta autoritativa da API.
- [x] Carregar opções de órgão, serviço, material e fornecedor do catálogo local para seleção explícita.
- [x] Preservar propostas não confirmadas, auditoria e arquivos originais; o catálogo continua não verificado.
- [x] Validar fila, formulário de edição, API de liberação, frontend e backend.
- Diagnóstico final: a regra de liberação estava quebrada por um filtro de organização em `backend/app/routes.py` que iterava sobre um valor booleano em vez de sobre os candidatos válidos; essa condição impedia o cálculo do checklist e a transição de documentos em quarentena.
- Validação final: backend `47 passed`; `npm run build` concluído. Avisos não bloqueantes: depreciação do `starlette.testclient`/`httpx` e bundle frontend acima de 500 kB.

### Etapa 33 — Dashboard restringido a faturas aprovadas (em implementação)
- [x] Ajustar o filtro do resumo financeiro do dashboard para ignorar documentos em `quarantined` e ler somente `invoice_workflow_state == "invoices"`.
- [x] Registrar teste de regressão para garantir que pendentes de avaliação manual não entrem no cálculo do dashboard por padrão.
- Decisão de negócio: o painel passa a considerar apenas faturas liberadas para o fluxo principal; documentos ainda em revisão permanecem fora do dashboard até aprovação manual.
- Validação executada: `pytest tests/test_domain_api.py -k 'approved_documents or invoice_document_cards_group_by_supplier_material_organization_and_service'` → 2 testes passaram.

### Etapa 32 — Reinicialização após conflito de porta (concluída)
- [x] Parar somente o processo identificado na porta 8000, conforme solicitado, e confirmar que as portas 8000 e 5173 ficaram livres.
- [x] Iniciar novamente o SIG-ES com o inicializador local e validar a API e a interface.
- Diagnóstico inicial: a porta 8000 está em `127.0.0.1` no PID 19400 (`python.exe`, executável `C:\python314\python.exe`), fora do ambiente virtual deste workspace; a porta 5173 está livre. Nenhum serviço Windows está associado ao PID.
- Limite: não reutilizar a instância Python externa nem presumir qual banco ela atende; iniciar usando as configurações do inicializador deste workspace.
- Resultado: PID 19400 encerrado; a API e o frontend foram iniciados pelo inicializador oficial em `127.0.0.1`. O healthcheck respondeu `ok`, com PostgreSQL conectado e ambiente `local_unverified`; a interface carregou e confirmou “API + postgresql: conectados”. O inicializador usa o fluxo configurado para o banco `SIG-SAMF` e migrações pendentes.
- Validação: `GET /api/v1/health` HTTP 200; interface `/dashboard` HTTP 200 e conexão confirmada visualmente. Sem alteração de código de aplicação.

### Etapa 31 — Inicialização do sistema por duplo clique (concluída)
- [x] Criar um arquivo `.bat` na raiz que execute `iniciar-siges.ps1` a partir de qualquer diretório.
- [x] Documentar o uso por duplo clique e manter visíveis requisitos/erros do inicializador.
- [x] Validar o lançador, o build da interface e testes do backend.
- Validação: o iniciador detectou corretamente a porta 8000 ocupada e parou sem iniciar serviços conflitantes; o PID 19400 pertence a outra aplicação (`SIGi-Certidões-v2.2`), que foi mantida em execução. Sintaxe PowerShell válida. `npm run build` concluído, com aviso conhecido de bundle >500 kB. Backend: 43 testes passaram e 2 falharam em `test_domain_api.py` (`release_ready` e revisão em lote retornando 422); nenhuma alteração foi feita nessa área.

### Etapa 29 — Inclusão de múltiplos campos pendentes (concluída)
- [x] Fazer cada seleção do menu “Adicionar campo à proposta” inserir imediatamente uma linha com entrada própria e ação de remoção.
- [x] Permitir incluir vários tipos de campo na mesma edição, com rótulo e tipo de entrada correspondente (por exemplo, data de vencimento como data e processo com formato de exemplo).
- [x] Enviar cada campo como proposta não confirmada ao salvar; exigir valor em cada linha e justificativa comum, mantendo os originais.
- [x] Mostrar a quantidade de campos no botão de salvar e apresentar erros dentro da janela.
- Validação: `npm run build` concluído; TypeScript/editor sem erros; conferência no navegador selecionando vencimento e processo mostrou as duas entradas editáveis e o botão “Salvar 2 campo(s)”. Nenhum dado de teste foi salvo. Aviso não bloqueante de bundle acima de 500 kB permanece.

### Etapa 28 — Edição explícita dos campos da quarentena (concluída)
- [x] Abrir o editor em “Adicionar campo” e exibir imediatamente o seletor com valor de fatura, termo, processo, vencimento, órgão, serviço, material e fornecedor.
- [x] Separar explicitamente adicionar novo campo de corrigir candidato existente, com seleção acessível dos candidatos registrados.
- [x] Não incluir candidatos já substituídos na lista de valores/candidatos editáveis, preservando os registros originais no banco e a trilha de auditoria.
- [x] Reconhecer referências únicas manuais de material/fornecedor no requisito de catálogo do checklist.
- [x] Testar cartão após correção e referência manual de material sem inferência da pasta.
- Validação: build frontend concluído; suíte backend `44 passed`; diagnósticos do editor sem erros. Permanece aviso não bloqueante do bundle acima de 500 kB. API local pode necessitar reinicialização para carregar mudanças de servidor.

### Etapa 27 — Diagnóstico da revisão e exibição de candidatos pendentes (análise concluída)
- O cartão compacto não exibe o checklist; ele aparece no detalhe e no formulário de edição. Após salvar, o frontend fecha o formulário e recarrega os dados.
- O checklist calcula valores/processo/data/órgão a partir de candidatos efetivos, mas a condição fornecedor/material consulta o material somente pela pasta (`_material_group_from_path`) e ignora um `material_reference` proposto manualmente.
- A lista `editable_candidates` inclui candidatos substituídos porque a API filtra por `review_state == candidate`, sem remover/identificar os IDs em `manual_proposal:prior:<id>`. O valor anterior e a proposta aparecem juntos, podendo confundir a revisão e a contagem resumida.
- A associação manual de fornecedor também é restringida pela compatibilidade com serviço/pasta; uma referência válida isolada pode não contar como grupo reconhecido.
- Correções do checklist de material/fornecedor e exclusão de candidatos substituídos da seleção corrente foram implementadas na Etapa 28; os registros originais permanecem preservados.

### Etapa 26 — Endereços diretos para as páginas (concluída)
- [x] Criar rotas para Dashboard, Faturas, Faturas pendentes, Documentos importados, Processos SEI, Alertas, Saldos, Auditoria e as abas de Configurações.
- [x] Atualizar o endereço ao navegar e sincronizar voltar/avançar do navegador.
- [x] Suportar acesso direto/recarga em páginas internas e normalizar `/` para `/dashboard`.
- Validação: `npm run build` concluído; navegador confirmou `/dashboard`, `/faturas`, `/configuracoes` e `/configuracoes/regras-administrativas`, além de voltar para `/dashboard`. Nenhum erro TypeScript; aviso não bloqueante de bundle acima de 500 kB permanece.

### Etapa 25 — Filtros de faturas por quatro dimensões (concluída no código)
- [x] Adicionar filtros por fornecedor, material, órgão e serviço.
- [x] Agrupar por referências únicas de catálogo/candidatos e por caminho relativo reconhecido; manter grupo não identificado quando a associação é ambígua ou ausente.
- [x] Incluir a associação de órgão nos dados da API, detalhes e pesquisa.
- [x] Cobrir os quatro valores de `group_by` no teste da API.
- Validação: suíte backend `44 passed`; `npm run build` concluído; diagnósticos do editor sem erros. A instância da API aberta no navegador respondeu HTTP 422 ao novo filtro de órgão porque ainda está executando código anterior; reiniciá-la para aplicar a mudança. Aviso não bloqueante do bundle >500 kB permanece.

### Etapa 24 — Resumo compacto e detalhe de faturas (concluída)
- [x] Manter nos cartões apenas arquivo, valor candidato da fatura, processo, vencimento e estado do fluxo.
- [x] Padronizar a altura dos cartões e tornar o resumo inteiro selecionável, com suporte a teclado.
- [x] Exibir em janela de detalhes as informações do documento, valores candidatos, classificação, evidências, estados, checklist de quarentena e acesso ao PDF original.
- [x] Manter a correção de candidatos disponível a partir do detalhe, sem alterar o fluxo de preservação do original.
- Validação: `npm run build` concluído; interação de abrir/fechar detalhes conferida no navegador e diagnósticos do editor sem erros. Aviso não bloqueante de bundle acima de 500 kB permanece.

### Etapa 23 — Alinhamento dos gráficos por órgão e por mês (concluída)
- [x] Posicionar “Valor por órgão” ao lado de “Evolução mensal” na mesma linha em telas largas.
- [x] Manter os cartões de serviços, materiais e fornecedores em uma linha separada e responsiva.
- [x] Validar o build e conferir visualmente os dois gráficos lado a lado em viewport desktop.
- Validação: `npm run build` concluído; TypeScript/editor sem erros. Aviso não bloqueante de bundle acima de 500 kB permanece.

### Etapa 22 — Separação dos cartões do dashboard por categoria (concluída)
- [x] Separar Serviços, Materiais e Fornecedores em cartões próprios.
- [x] Ajustar o grid para quatro cartões no desktop, duas colunas em telas médias e uma em telas estreitas.
- [x] Preservar as agregações, contagens, avisos de associação segura e identificação dos valores em BRL como candidatos.
- Validação: `npm run build` concluído; TypeScript/editor sem erros. Permanece apenas o aviso conhecido de bundle acima de 500 kB. Interface conferida no ambiente local; API/banco indisponíveis durante a conferência.

### Etapa 21 — Exposição do status do monitor pela API (concluída)
- [x] Retornar status ativo/inativo e raiz monitorada em `GET /api/v1/monitor/status`.
- [x] Cobrir configurações com monitor ativo e sem monitor em testes da API.
- Restrição: revelar a raiz local somente neste endpoint operacional solicitado; manter a API em loopback e não registrar o caminho em logs nem persistir caminho absoluto.
- Validação: suíte completa do backend — 44 testes aprovados; um aviso de depreciação do `starlette.testclient`/`httpx` permanece não bloqueante.

### Etapa 11 — Execução demonstrativa em rede local (iniciada)
- [x] Iniciar API e frontend vinculados às interfaces de rede locais.
- [x] Verificar saúde da API e carregamento da interface pela rede local.
- Resultado: frontend disponível em `http://192.168.0.112:5173/`; API disponível em `http://192.168.0.112:8000/`; `/api/v1/health` respondeu `status=ok`, com SQLite demonstrativo conectado.
- Limites: execução somente demonstrativa, com dados sintéticos, SQLite local e sem monitoramento, autenticação ou integrações institucionais habilitados.

### Etapa 12 — Conexão PostgreSQL local existente (iniciada)
- [x] Identificar falha do preflight causada pela tabela `administrative_rule_drafts` não reconhecida.
- [x] Atualizar a lista de tabelas SIG-ES esperadas sem remover nem alterar dados.
- [ ] Validar migrações e iniciar a API usando o PostgreSQL local existente.
- Limites: a senha continua sendo solicitada somente no terminal; nenhuma credencial é registrada ou exibida pela aplicação.

### Etapa 14 — Inicializador PowerShell do sistema completo (iniciada)
- [x] Criar script único para iniciar API com PostgreSQL e interface web.
- [x] Manter senha oculta, monitoramento obrigatório e acesso somente local.
- [x] Validar sintaxe, testes e documentar o comando `cd frontend; npm run dev`.
- O monitor exige uma raiz local existente e autorizada; por padrão usa `C:\2026`. O iniciador interrompe se a pasta não existir ou se as portas 8000/5173 estiverem ocupadas.
- Validação: parser PowerShell e JSON válidos; `npm run build` concluído (aviso não bloqueante de bundle acima de 500 kB); backend `41 passed`.

### Etapa 15 — Classificação de valores na tela Faturas (concluída)
- [x] Separar classificação do número (total, parcela, percentual, juros, encargo, multa, desconto, imposto, tarifa, preço unitário, quantidade e outro número) da natureza bruto/líquido.
- [x] Persistir a classificação proposta sem alterar nem confirmar o candidato original, por meio de migração aditiva.
- [x] Limitar a nova opção de classificação à tela Faturas; fluxo de pendências e aplicação das regras em Configurações ficam para etapas posteriores.
- [x] Excluir das somas financeiras candidatos explicitamente classificados como não totais; a proposta também substitui o original apenas nas agregações, preservando ambos os registros para proveniência.
- Validação: 42 testes do backend passaram; build TypeScript/Vite concluído com aviso não bloqueante de bundle >500 kB.

### Etapa 16 — Classificação de valores em Faturas pendentes (iniciada)
- [x] Exibir no formulário de pendências as opções de tipo de número já disponíveis em Faturas.
- [x] Enviar e persistir a classificação na proposta sem confirmar nem sobrescrever a extração original.
- [x] Validar build, API e testes relevantes.
- Validação: `npm run build` concluído; backend `42 passed`; diagnósticos do editor sem erros.

### Etapa 17 — Fluxo de quarentena e revisão de faturas (iniciada)
- [x] Persistir estado de quarentena/liberada no documento e registrar transições em auditoria.
- [x] Liberar para Faturas somente quando campos de revisão e classificação estiverem completos e sem ambiguidades.
- [x] Adicionar retorno à revisão no editor de Faturas.
- [x] Validar testes da API, migração e build do frontend.
- Checklist de liberação: total da fatura único e classificado; todos os números candidatos classificados; processo e vencimento únicos; fornecedor/material reconhecido; órgão único associado.
- A transição para Faturas é apenas estado de workflow; não confirma pagamento, autenticidade ou validação externa. A migração `0005_invoice_quarantine_workflow` coloca documentos existentes em quarentena e preserva arquivos e candidatos.
- Validação: backend `43 passed`; migração até `0005_invoice_quarantine_workflow` em SQLite descartável; build do frontend concluído (aviso de bundle >500 kB).

### Etapa 18 — Remoção de conteúdo sintético ativo e auditoria de produção (concluída)
- [x] Remover faturas, alertas, usuário, eventos e vínculos fictícios das telas ativas.
- [x] Ligar telas de processos e alertas às listas persistidas reais ou exibir estado vazio explícito.
- [x] Remover botões sem implementação e evitar alegar que o sistema está homologado/produção.
- [x] Executar build e testes e reportar bloqueadores de produção.
- Removido o dataset frontend de faturas/alertas/distribuições sintéticas, o perfil fixo, o contador de alertas, a saudação nominal, cartões SEI e a linha do tempo inventados, além de controles que apenas exibiam avisos.
- Healthcheck agora informa `local_unverified`; a interface informa “Ambiente local · não homologado”. Dados extraídos continuam identificados como candidatos e catálogos como não verificados.
- Auditoria detalhada e gates de produção registrados em `docs/auditoria-prontidao-producao.md`.
- Validação: build frontend concluído com aviso de bundle >500 kB; backend `43 passed`.
- Resultado de prontidão: **não aprovado para produção**; autenticação/autorização, decisão explícita de aceite humano, fontes oficiais, trilha auditável atribuída a usuário, reconciliação do monitor e plano operacional/backup ainda faltam.

### Etapa 19 — Reinicialização da instância atualizada (concluída)
- [x] Reiniciar API PostgreSQL e frontend após a remoção de dados sintéticos e atualização do healthcheck.
- [x] Confirmar `environment=local_unverified`, banco conectado e ausência de dados fictícios na interface.
- Limite: reiniciar o monitor baseado em eventos não faz backfill dos arquivos existentes nem recupera eventos ocorridos enquanto parado.
- Verificação: API `ok`, `local_unverified`, PostgreSQL conectado, monitor ativo, `parsed=0`, `errors=0`; navegador mostra API/PostgreSQL conectados, sem registros fictícios.

### Etapa 20 — Manutenção do aviso de não homologação (concluída)
- [x] Registrar que “Ambiente local · não homologado” é um aviso operacional, não conteúdo demonstrativo.
- [x] Manter explícito que valores extraídos são candidatos e que pagamento, saldo e existência no SEI não estão confirmados.
- Decisão: não retirar nem suavizar o estado de não homologação até implementar e validar autenticação/autorização, aceite humano rastreável e fontes oficiais. A conectividade PostgreSQL, por si só, não caracteriza produção.
- Nenhuma alteração de interface realizada nesta etapa.

### Etapa 13 — Documentação funcional consolidada (concluída)
- [x] Criar explicação em português sobre telas, API, banco, ingestão, extração, revisão e monitoramento.
- [x] Registrar de forma explícita os limites atuais e os recursos ainda não implementados.
- [x] Linkar a documentação no README.

## Escopo solicitado
Aplicação web corporativa para apoiar o monitoramento e a gestão de faturas, documentos e processos SEI, com dashboard, revisão de extrações, integração futura com planilha de saldos, regras por pasta, alertas, controle de acesso e auditoria.

## Decisões seguras da Etapa 1
- Workspace inicial estava vazio.
- Base planejada: frontend React + TypeScript + Vite; API Python + FastAPI.
- O protótipo utiliza apenas dados sintéticos explicitamente marcados como demonstração.
- Nenhuma conexão a `C:\2026`, pasta de rede, SEI, Active Directory ou SMTP será ativada nesta etapa.
- O protótipo não altera arquivos externos e não toma decisões financeiras oficiais.

## Etapas e entregas
### Etapa 1 — Fundação e protótipo navegável (concluída)
- [x] Criar estrutura mínima do frontend e backend.
- [x] Implementar navegação e telas demonstrativas principais.
- [x] Criar documentação inicial, pressupostos e pendências.
- [x] Validar build do frontend e testes básicos da API.

**Implementado nesta etapa:**
- Frontend React + TypeScript + Vite com navegação responsiva: Dashboard, Faturas, Processos SEI, Alertas, Saldos, Auditoria e Configurações.
- Dashboard com KPIs, gráficos sintéticos por período/órgão/serviço, filtro por período/status, pesquisa, lista de faturas, alertas de demonstração e detalhe de fatura.
- Banner visível de ambiente demonstrativo; telas explicam que vínculos, alertas, confiança e registros são fictícios.
- Backend FastAPI com endpoint `GET /api/v1/health`; CORS limitado aos endereços de desenvolvimento local e sem integrações ativas.
- README, instruções do workspace, decisões e pendências, dependências e teste inicial de saúde.
- Os arquivos monitorados, compartilhamentos, SEI, e-mail e serviços de identidade não são acessados.

**Validação executada:**
- `npm install` e `npm run build` no frontend: concluídos. Vite emitiu aviso não bloqueante de bundle JavaScript acima de 500 kB.
- `python -m pip install -r requirements.txt` e `python -m pytest` no backend: 1 teste aprovado. Há aviso de depreciação do `TestClient` por combinação futura de dependências; revisar ao atualizar a stack.
- Instalação npm reportou zero vulnerabilidades conhecidas no momento da instalação.

**Limites atuais:** sem persistência, autenticação, ingestão/OCR, integrações, auditoria persistente ou cálculos com dados oficiais. Não utilizar para decisões administrativas ou financeiras.

### Etapa 2 — Modelo de domínio e persistência (concluída)
- [x] Definir entidades técnicas iniciais sem cristalizar regras institucionais pendentes.
- [x] Implementar persistência local e endpoints iniciais.
- [x] Adicionar testes de persistência e API.

**Implementado nesta etapa:**
- Modelos SQLAlchemy para órgãos e serviços (catálogos vazios), documentos de origem, candidatos de extração, faturas, processos SEI, vínculos, alertas e eventos de auditoria.
- Estados de revisão, pagamento e verificação SEI separados; pagamentos começam como `unknown` e processos como `unverified`.
- API FastAPI de leitura paginada para faturas, processos e alertas; listas vazias até que dados sejam inseridos por fluxo autorizado futuro.
- Constraints e índices básicos; migração Alembic inicial e SQLite local configurável por `SIGES_DATABASE_URL`.
- Testes isolados em SQLite em memória, sem documentos ou dados institucionais.
- Documentação do modelo em `docs/modelo-dominio-inicial.md` e instruções de migração atualizadas.

**Validação executada:**
- `pytest`: 4 testes aprovados (saúde, listagem vazia, leitura de registro persistido e limite de paginação).
- `alembic upgrade head`: migração inicial aplicada com sucesso em banco SQLite descartável de validação.
- Revisão dos arquivos Python: sem diagnósticos reportados pelo editor.

**Limites atuais:** API somente leitura e sem autenticação; manter estritamente local. Migração inicial deriva do metadata SQLAlchemy e deve ser revisada/substituída por migration explícita antes de produção. Sem CRUD, scanner, extração, integração ou geração automática de alertas.

### Etapa 3 — Ingestão segura e revisão humana (concluída parcialmente)
- [x] Criar descoberta somente leitura, sem raiz padrão e sem seguir links simbólicos.
- [x] Gerar hash e identificador seguro relativo, com deduplicação idempotente no índice.
- [x] Testar exclusivamente em diretório temporário sintético.
- [x] Documentar limites: ainda sem OCR, leitura de conteúdo ou revisão UI/API.

**Implementado nesta etapa:**
- Biblioteca explícita `backend/app/scanner.py`; não é executada automaticamente e não possui raiz padrão.
- Whitelist inicial de extensões, limite configurável de tamanho, verificação de raiz resolvida, exclusão de symlinks e captura de erros recuperáveis.
- Hash SHA-256 por blocos, detecção de arquivo alterado durante leitura, metadados com caminho relativo e MIME inferido.
- Indexação SQLAlchemy idempotente por fonte + caminho relativo + hash; substituições de conteúdo preservam registro distinto.
- Testes usam somente `tmp_path` e incluem extensão, conteúdo inalterado, tamanho, chave inválida, symlink (quando permitido) e repetição/substituição.
- Guia técnico criado em `docs/ingestao-segura.md`.

**Validação executada:**
- `pytest`: 9 testes aprovados. Um teste de symlink é marcado como skip apenas se a política do Windows impedir a criação do link.
- Diagnósticos do editor em scanner e testes: nenhum erro reportado.

**Limites atuais:** scanner não foi executado contra `C:\2026` nem share real; não há watchdog, scheduler, CLI, estabilidade/espera do arquivo, parser PDF/XLSX/DOCX, OCR, extração, fila de revisão ou endpoint de ingestão.

### Etapa 4 — Inventário histórico e ingestão local (em andamento)
- [x] Inventariar recursivamente metadados sem abrir conteúdo.
- [ ] Ingerir documentos suportados em lotes com hash e extração em candidatos.
- [ ] Manter fontes, valores e estados rastreáveis, sem confirmar fatos financeiros.
- [ ] Expor resumo e fila de revisão na API/interface.

### Etapa 4 — Extração documental determinística (concluída parcialmente)
- [x] Ler texto de PDF e conteúdo tabular/documental sem executar macros.
- [x] Gerar candidatos a campos com método e localização da evidência.
- [x] Persistir candidatos idempotentemente sem confirmar dados.
- [x] Cobrir parsers com documentos sintéticos; OCR permanece desligado.

**Implementado nesta etapa:**
- Parsers locais para PDF digital (`pypdf`), XLSX/XLSM (`openpyxl` read-only) e DOCX (`python-docx`).
- Candidatos sintáticos a número SEI, montantes com prefixo R$ e datas com rótulo de vencimento; valor normalizado como decimal textual.
- Evidência por página, célula/aba ou parágrafo/tabela; score de confiança permanece nulo.
- Limites de arquivo, páginas, células, abas e conteúdo descompactado; fórmulas ignoradas, macros não executadas, PDF criptografado recusado.
- Persistência idempotente de candidatos em estado `candidate`, sem escrita de dados confirmados.
- Guia em `docs/extracao-deterministica.md`; fixtures sintéticas cobrem os três formatos e deduplicação.

**Validação executada:**
- `pytest`: 15 testes aprovados em toda a suíte.
- Diagnósticos do editor nos parsers e endpoints: nenhum erro reportado.

**Limites atuais:** heurísticas ainda não calibradas com layouts institucionais; sem OCR, CNPJ, número de fatura, confirmação automática, tela/fila de revisão, endpoint protegido ou evidência oficial.

### Etapa 5 — Prévia configurável de planilha (concluída parcialmente)
- [x] Ler planilha local somente com mapeamento explícito, sem caminho/aba/colunas padrão.
- [x] Validar linhas, valores decimais e competência; gerar relatório de prévia sem persistir.
- [x] Testar com XLSX sintético; nenhum arquivo de rede será acessado.

**Implementado nesta etapa:**
- Parser read-only de XLSX/XLSM com aba, cabeçalho, colunas e formato de período fornecidos explicitamente pelo chamador.
- Mapeamento por letras de coluna ou cabeçalho único; valores monetários em Decimal; períodos normalizados para o primeiro dia do mês.
- Fórmulas são rejeitadas para evitar usar valores calculados não validados; macros e vínculos externos não são carregados.
- Prévia em memória com hash da fonte, células de origem, linhas aceitas e códigos de rejeição sem ecoar valores financeiros.
- Sem caminho padrão, share, persistência, associação automática a órgão ou cálculo de saldo projetado.
- Guia criado em `docs/pre-visualizacao-saldos.md`.

**Validação executada:**
- `pytest`: 19 testes aprovados, incluindo workbook sintético, mapeamento por coluna/cabeçalho, fórmulas e integridade da fonte.

**Limites atuais:** não foi lida planilha institucional. Importação persistente, freshness, reconciliação com faturas e alertas dependem da definição oficial de colunas, chaves de órgão, período e significado de saldos.

### Etapa 5 — Revisão dos candidatos importados e integração do painel (em andamento)
- [ ] Validar resumo da ingestão persistida e confirmar quantidade de documentos/candidatos no banco.
- [ ] Rever e classificar candidatos por campo, evidência e relevância sem confirmar valores financeiros.
- [ ] Exibir dados reais na tela de documentos importados e manter o estado de revisão explícito.
- [ ] Preparar a próxima fase de alertas e regras de saldo com base em campos confirmados e rastreáveis.

**Implementado nesta etapa:**
- Persistência real confirmada no PostgreSQL com 196 documentos e 6.660 candidatos em estado `candidate`.
- Endpoints de resumo e listagem de candidatos já disponíveis em [backend/app/routes.py](backend/app/routes.py) e consumidos pela página de documentos importados em [frontend/src/App.tsx](frontend/src/App.tsx).
- Regras de segurança mantidas: os dados são somente leitura, as fontes originais são preservadas e nenhuma confirmação financeira foi aplicada.

**Validação executada:**
- `GET /api/v1/ingestion/summary` retornou contagem de documentos, candidatos e pendências.
- `GET /api/v1/extraction-candidates?limit=3&offset=0` retornou registros reais com `relative_path`, `field_name`, `raw_value` e `review_state`.
- A interface do frontend foi iniciada em `127.0.0.1:5173`, mas as chamadas do navegador continuam dependentes da API local ativa.

### Etapa 6 — Regras de saldo e alertas (não iniciada)
- [ ] Confirmar significado de saldo/período e condições de alerta antes de ativar cálculos.
- [ ] Implementar alertas explicáveis e persistentes após aprovar as regras.

### Etapa 6 — Catálogo informado e valor do termo (em andamento)
- [ ] Substituir listas de catálogo inventadas pelos arrays do JSON enviado pelo usuário, preservando vínculos fornecedor-serviço.
- [ ] Diferenciar candidatos de valor da fatura e de termo de recebimento com evidência por página e precedência explícita.
- [ ] Expor no painel apenas contagens/resumos reais da API e candidatos rastreáveis; não tratar candidatos como registros financeiros confirmados.
- [ ] Testar extração, precedência, catálogo e build da interface.

### Etapa 7 — Dashboard por valor candidato do termo (em andamento)
- [x] Agregar por documento e usar somente valor de termo de recebimento não ambíguo.
- [x] Expor agregações por órgão, mês de referência do arquivo, serviço e material com metadados de exclusão/proveniência.
- [x] Fazer gráficos Power BI-like preservando o layout aprovado e sem chamar candidatos de gastos confirmados.
- [x] Testar somas, precedência e exclusão de ambiguidades.

### Etapa 7 — Segurança, auditoria e operação (não iniciada)
- [ ] Permissões, auditoria, observabilidade, backup/restauração e hardening.

### Etapa 9 — Faturas pendentes e propostas de correção (em andamento)
- [x] Criar submenu Faturas > Pendentes, agrupado por fornecedor ou material.
- [x] Permitir corrigir candidatos e adicionar campos ausentes com justificativa, inclusive classificar valores como bruto/líquido/indefinido.
- [x] Gravar propostas como novos candidatos pendentes e trilha de auditoria, sem confirmar fatos financeiros.
- [x] Garantir que todos os PDFs de fatura permaneçam pendentes até revisão humana.
- [x] Testar validação por tipo de campo, classificação monetária e tentativa de duplicidade.

### Etapa 10 — Regras administrativas por fornecedor e material (em andamento)
- [x] Organizar Configurações como aba principal e ocultar suas subabas até abrir a seção.
- [ ] Criar cartões de regra para cada fornecedor e material com abertura da seção de edição.
- [ ] Configurar cobrança exclusiva/rateio, método de rateio ainda não definido, e natureza bruta/líquida separada para fatura e termo.
- [ ] Manter versões como rascunho auditável, sem aplicar regras à extração nem escolher um valor automaticamente.
- [ ] Indicar divergências entre fatura e termo para revisão humana; preservar ambos os candidatos e respectivas evidências.
- [ ] Testar persistência, histórico, validação dos catálogos e build/interface.

### Etapa 8 — Cartões de PDFs por fornecedor/material (em andamento)
- [ ] Listar PDFs reais com candidatos e proveniência em cartões paginados.
- [ ] Separar alternância por fornecedores e materiais; serviços ficam como vínculo do fornecedor, não como terceiro agrupamento.
- [ ] Abrir arquivo original somente da raiz monitorada e após validar hash, sem modificar o conteúdo.
- [ ] Testar classificação, paginação, path traversal e estado de API desativada.

### Etapa 8 — Homologação e implantação (não iniciada)
- [ ] Validar com dados anonimizados, benchmark, aceite e runbooks.

## Perguntas ainda abertas
1. O serviço será executado em Windows Server, Linux ou estação Windows? Como o processo terá acesso autorizado aos compartilhamentos?
2. Qual é a árvore real de pastas e quais são os tipos e tamanhos típicos dos arquivos?
3. Qual é a planilha oficial, sua aba, cabeçalhos, período e definição exata de saldo disponível?
4. Qual sistema/fonte comprova pagamento e qual é o fluxo de aprovação das faturas?
5. Quais são os órgãos, serviços, regras de SEI e rateio oficialmente aplicáveis?
6. Qual provedor de identidade está disponível (AD/LDAP/Entra/contas locais) e quais papéis/escope por órgão são necessários?
7. Existe integração SEI documentada e autorizada? Se sim, fornecer documentação e ambiente de homologação.
8. Quais são requisitos institucionais de retenção, LGPD, auditoria, disponibilidade e backup?

## Histórico
- 28/09/2026 — Aprimoradas também as subabas: menu lateral ganhou linha de hierarquia, ícones e áreas clicáveis maiores; abas internas de Configurações ganharam contorno/realce da selecionada. Verificado em viewport compacto e desktop; build frontend aprovado.
- 28/09/2026 — Refinado o layout de Configurações: cabeçalho contextual, subabas com estado ativo legível, preferências agrupadas e atalhos de segurança/regras; telas médias estreitam a sidebar, simplificam o banner de status e empilham os princípios das regras. Verificado em viewport 810×346 e build frontend aprovado; permanece aviso conhecido de bundle acima de 500 kB.
- 28/09/2026 — Adicionado scroll vertical independente ao menu lateral; cabeçalho, seletor de workspace e rodapé permanecem fixos. Build passou; verificado `overflow-y: auto` e que o menu rola em viewport curto.
- 28/09/2026 — A pedido, Configurações foi movida do topo para o grupo “SISTEMA”, abaixo de Auditoria, mantendo subabas recolhíveis. Build frontend aprovado e posição verificada após recarregar.
- 28/09/2026 — Após relato de dificuldade para localizar Configurações, movida a aba para logo abaixo de Dashboard no topo da navegação lateral. Recarregada e verificada a interface: Configurações abre o submenu, e Regras administrativas abre a tela de regras. Build frontend aprovado.
- 28/09/2026 — Ajustada a navegação: “Faturas > Pendentes” fica oculta até expandir Faturas; Regras administrativas foi movida para subaba em Configurações, junto a Geral, e cartões abrem o editor inline. Navegador confirmou a navegação e a abertura do editor do fornecedor BRK; API confirmou 22 fornecedores, 6 materiais, regras em rascunho e nenhuma aplicação automática. Build frontend aprovado; sem alteração de banco nesta reorganização.
- 28/09/2026 — Etapa 6 em execução: catálogo de referência substituído pelos dados enviados pelo usuário (11 órgãos, 6 materiais, 45 serviços, 22 fornecedores e vínculos); endpoint informa que a lista é referência não verificada. Extração distingue valores candidatos de fatura/termo com precedência do termo, reconhece itens catalogados com proveniência e o monitor passa a extrair novos/alterados arquivos após indexar metadados. Dashboard e fila de ingestão mostram dados da API e deixam explícito o estado candidato. Validação: 32 testes backend e build frontend aprovados; warning existente do TestClient/httpx permanece. Reprocessamento idempotente da raiz autorizada `C:\2026` foi iniciado para atualizar candidatos históricos, mas seu resumo final ainda está pendente.
- 28/09/2026 — Ajuste visual do dashboard a pedido: restaurada a composição de referência com quatro KPIs, três gráficos em linha, lista recente à esquerda e painel operacional à direita. O conteúdo permanece conectado a contagens reais de ingestão (pastas, tipos de arquivo e campos candidatos); nenhuma série temporal financeira ou alerta fictício foi reintroduzido. Build TypeScript/Vite e verificação visual no navegador concluídos.
- 28/09/2026 — Etapa 7 validada em execução: endpoint `GET /api/v1/dashboard/financial-candidates` soma exclusivamente valor de termo único por documento atual; exclui documento com múltiplos valores de termo, não substitui termo ausente por valor da fatura, só atribui órgão/serviço/material com referência única e só atribui mês quando consta no nome do arquivo. O dashboard usa pizza por órgão, evolução mensal e barras roláveis para todo o catálogo de serviços/materiais. `pytest`: 33 testes aprovados; `npm run build` aprovado. API reiniciada e validada: health OK, endpoint financeiro retorna 292 documentos incluídos, R$ 4.542.347,37 em candidatos de termos, 126 documentos ambíguos excluídos; monitor ativo. Reprocessamento histórico também terminou, mas reportou 54 arquivos com erro (35 DataError, 9 limite de células, 8 AttributeError e 2 PdfReadError); preservar os estados de erro para revisão, sem promover valores.
- 28/09/2026 — Refinamento do dashboard: removidas as seções “Extrações recentes” e “Estado da ingestão” da página principal; donut por órgão e painel de barras de serviços/materiais ficam lado a lado; evolução mensal ocupa a largura completa abaixo. A fila detalhada permanece em Documentos importados. Build frontend aprovado e endpoint financeiro conferido ativo.
- 28/09/2026 — Etapa 8 implementada em código: listagem paginada de PDFs sob MATERIAL/SERVIÇO, agrupamento alternável por fornecedor/material, cartões com valor candidato/processo/evidência e botão inline para PDF. A abertura confina ao monitor root, rejeita symlinks/path traversal e confere SHA-256 antes de transmitir. Fornecedor mantém o serviço associado no cartão em vez de virar grupo paralelo. Testes backend: 36 aprovados; build frontend aprovado. A instância API atualmente ativa responde 404 ao novo endpoint por ainda ser processo anterior às alterações; reinício está aguardando senha PostgreSQL no terminal atual.
- 27/09/2026 — Iniciado complemento da Etapa 2 após informação do usuário de que PostgreSQL está instalado. Antes de alterar dependências/configuração, registrado que host, porta, banco, usuário e credenciais não foram informados; nenhum segredo será solicitado ou gravado no repositório.
- 27/09/2026 — Adicionado psycopg 3 e suporte de URL `postgresql+psycopg://`; URL validada para dialetos aceitos e escape de caracteres percentuais no Alembic.
- 27/09/2026 — Serviço Windows `postgresql-x64-18` encontrado em execução; `psql` não está no PATH. Não foi tentada conexão porque faltam banco, usuário e permissões; nenhuma senha foi solicitada nem alteração feita no serviço.
- 27/09/2026 — Suíte completa aprovada: 19 testes em SQLite isolado após instalar o driver; conexão/migração PostgreSQL continuam pendentes de URL configurada pelo responsável.
- 27/09/2026 — Usuário solicitou conectar a aplicação e informou que fornecerá a senha diretamente no terminal. Serviço PostgreSQL 18 está ativo em localhost:5432; próximo passo depende apenas do nome do banco e usuário autorizados. Senha não será solicitada no chat nem registrada.
- 27/09/2026 — Usuário informou que o banco PostgreSQL se chama `SIG-SAMF`. Ainda falta confirmar o usuário/role autorizado; host/porta observados são localhost:5432. O nome foi registrado exatamente como informado, incluindo maiúsculas e hífen.
- 27/09/2026 — Usuário confirmou role `junior.pareschi` e digitou a senha diretamente no prompt oculto. Pré-verificação terminou com `OperationalError`; nenhuma migração foi aplicada e a API não foi iniciada. Diagnóstico precisa distinguir autenticação, role, database e conectividade sem registrar senha/URL.
- 27/09/2026 — Usuário informou que a senha digitada estava correta. Repetir a pré-verificação com diagnóstico SQLSTATE/mensagem do servidor para identificar se a falha é nome do banco/role, método de autenticação ou acesso; nenhuma senha será registrada.
- 27/09/2026 — Usuário informou que a autenticação do role de aplicação falha e solicitou troca de senha. Iniciada recuperação usando somente o cliente PostgreSQL e prompts interativos; senha antiga/nova não será enviada ao chat nem registrada. Alteração exige autenticação como superusuário/role administrador autorizado.
- 27/09/2026 — Tentativa de abrir `psql` como role administrativo `postgres` falhou com `FATAL: autenticação do tipo senha falhou`; nenhuma alteração foi feita. Próxima opção segura é recuperar o acesso administrativo com responsável da máquina ou procedimento local estritamente temporário e restrito, sem deixar autenticação `trust` habilitada.
- 27/09/2026 — Segunda tentativa da senha administrativa `postgres` também falhou com autenticação inválida. Nenhuma senha foi alterada e nenhuma migração executada. Parar novas tentativas; solicitar ao administrador da instância que redefina a credencial ou forneça role autorizada. Após isso, testar role `junior.pareschi` no banco `SIG-SAMF` e migrar apenas após preflight.
- 27/09/2026 — Em uma sessão administrativa `psql` autenticada, tentativa de redefinir `junior.pareschi` respondeu `role does not exist`; a senha não foi alterada. `\du` mostrou apenas a role `postgres`; consulta a `pg_database` mostrou apenas `postgres` e `samf` (owner `postgres`), não `SIG-SAMF`. Migração interrompida, sem modificar bancos; confirmar se deve usar o banco existente `samf` ou criar o banco `SIG-SAMF` e criar uma role de aplicação.
- 27/09/2026 — Usuário autorizou explicitamente criar um banco novo `SIG-SAMF` e uma role LOGIN `junior.pareschi` sem superusuário. O banco existente `samf` não será alterado. Próximo: criar role e database dedicado, definir senha via `\password` em prompt oculto e só então aplicar migrações.
- 27/09/2026 — Confirmado no `psql`: role LOGIN `junior.pareschi` e banco `SIG-SAMF` (owner da role) foram criados. `\password` retornou ao prompt `postgres=#` sem erro; senha definida não foi mostrada. Próximo passo: testar a aplicação com essa role e migrar o schema SIG-ES.
- 27/09/2026 — Pré-verificação da aplicação conectou a `SIG-SAMF` como `junior.pareschi`, PostgreSQL 18.6; schema `public` estava vazio. Alembic aplicou `0001_initial` com sucesso.
- 27/09/2026 — API iniciada apenas em `127.0.0.1:8000`; health respondeu `ok`, `database=connected`, `database_engine=postgresql`. Endpoints de faturas e processos responderam com zero registros, conforme esperado para banco novo.
- 27/09/2026 — Frontend Vite iniciado em `127.0.0.1:5173`; resposta HTTP 200. A UI continua em modo demonstração, sem consumir registros reais dos endpoints ainda.
- 27/09/2026 — Uma credencial administrativa foi colada em texto claro na conversa durante o troubleshooting; não a repetir ou armazenar. Recomendar rotação imediata dessa credencial administrativa. A senha de aplicação foi inserida apenas em prompt oculto e não foi registrada pelo projeto.
- 27/09/2026 — Usuário autorizou monitorar sua cópia local em `C:\2026`. Iniciada etapa de leitura somente; verificar escopo e segurança antes de qualquer varredura. Nenhum arquivo será alterado, movido ou removido.
- 27/09/2026 — Raiz `C:\2026` confirmada; listagem imediata mostrou `EXECUTADO & PROGRAMADO`, `RATEIO` e `DESEMPENHO ANUAL (2026).xlsx`. Enumeração recursiva histórica foi interrompida por lentidão; não será repetida automaticamente.
- 27/09/2026 — Implementado watchdog opt-in, indexação de metadados/hash somente leitura, status de monitoramento sem caminho absoluto, configuração explícita `-MonitorRoot` e indicador de UI; sem backfill de arquivos existentes, extração ou OCR.
- 27/09/2026 — Testes backend: 23 aprovados; build frontend aprovado. Avisos: `TestClient`/httpx depreciação e bundle JS acima de 500 kB.
- 27/09/2026 — API reiniciada com `-MonitorRoot 'C:\2026'`; health confirmou PostgreSQL conectado e `/api/v1/monitor/status` confirmou `running=True`, fonte `local-copy-2026`, 0 em fila, 0 indexados e 0 erros no momento da checagem. Frontend respondeu HTTP 200 em `127.0.0.1:5173`.
- 27/09/2026 — Usuário solicitou ler todo o conteúdo e aplicar os dados da cópia `C:\2026`. Iniciada ingestão histórica local em etapa própria: primeiro inventário/contagens, depois candidatos extraídos e persistidos com proveniência; não confirmar pagamento, autenticidade SEI, órgão ou saldo sem evidência/revisão.
- 27/09/2026 — Inventário metadata-only concluído: 1.014 arquivos, 1.320.529.137 bytes, 0 erros, profundidade máxima 4; 951 PDF, 44 XLS legado, 15 XLSX, 2 XLSM e 2 sem extensão. Foram agrupados 54 caminhos de pasta até profundidade 3. Nenhum conteúdo foi lido nesta contagem.
- 27/09/2026 — Parsers estendidos a XLS legado e CSV e extração por linha; ingestão histórica local e APIs de candidatos/documentos implementadas. 28 testes backend passaram; build frontend aprovado. Antes da ingestão real, será parado o monitor/API para liberar a conexão PostgreSQL; depois a execução emitirá apenas contagens/progresso e códigos de erro.
- 27/09/2026 — Ingestão histórica em execução; checkpoints: 150 documentos/4.683 candidatos; 175 documentos/5.853 candidatos novos; 11 falhas observadas até o checkpoint mais recente. Pypdf emitiu avisos repetidos de fonte CFF/MyriadPro sem fontTools; prosseguir somente com candidatos e registrar falhas/limitações no resumo final.
- 27/09/2026 — Usuário autorizou prosseguir após digitar a senha. API consultada: ingestão prévia parcial de 196 documentos, 6.660 candidatos pendentes, 7 estado error e 5 ainda discovered; sem alterações nos arquivos locais. A retomada será idempotente, com suporte fontTools instalado.
- 27/09/2026 — API iniciada novamente em `127.0.0.1:8000`; health confirmou PostgreSQL conectado. Esta invocação não incluiu `-MonitorRoot`, portanto monitor de eventos está desativado nela. A sessão de ingestão histórica separada permanece aguardando senha em prompt oculto; API não substitui esse job.
- 27/09/2026 — Iniciada Etapa 1; criado este registro antes da implementação. Nenhuma integração real está habilitada.
- 27/09/2026 — Etapa 1 concluída e validada como protótipo; build frontend aprovado e teste inicial da API aprovado. Registrados limites e aviso de bundle/dependência acima.
- 27/09/2026 — Iniciada Etapa 2 antes de editar o modelo: persistência e API serão preparadas para desenvolvimento sem fontes oficiais.
- 27/09/2026 — Etapa 2 concluída e validada: 4 testes passaram e migração inicial aplicada em SQLite isolado; registrada a limitação de API sem autenticação.
- 27/09/2026 — Iniciada Etapa 3 antes de alterações: scanner será uma biblioteca explicitamente invocada, sem caminho padrão e testada somente com fixtures temporárias.
- 27/09/2026 — Etapa 3 concluída parcialmente: scanner seguro e indexação idempotente implementados; 9 testes passaram. Nenhum caminho institucional foi acessado.
- 27/09/2026 — Iniciada Etapa 4 antes de editar parsers: extração será determinística e local, manterá evidência por página/célula e não fará OCR nem confirmação automática.
- 27/09/2026 — Etapa 4 concluída parcialmente: parsers PDF/XLSX/XLSM/DOCX criam candidatos rastreáveis e persistem sem confirmação; 15 testes passaram.
- 27/09/2026 — A pedido, Etapa 2 revalidada sem reimplementação: 4 testes direcionados de saúde/API passaram; a Etapa 2 já estava concluída. Permanece o aviso de depreciação do `TestClient`.
- 27/09/2026 — Iniciada Etapa 5: será implementada prévia de workbook baseada em mapeamento explícito, sem conexão ao caminho compartilhado nem gravação.
- 27/09/2026 — Etapa 5 concluída parcialmente: prévia de planilha validada com XLSX sintético; 19 testes passaram; nenhuma fonte de rede foi acessada.
