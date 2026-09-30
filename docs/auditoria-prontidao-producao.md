# Auditoria de remoção de dados sintéticos e prontidão de produção

**Data:** 29/09/2026  
**Escopo:** inspeção estática do workspace e limpeza do conteúdo sintético ativo na interface. Não foram abertos PDFs, consultados o SEI, lidos compartilhamentos, ingeridos arquivos, alteradas regras administrativas nem consultadas credenciais.

## Resultado executivo

Os registros sintéticos embutidos na interface foram removidos. As áreas de processos e alertas agora consultam endpoints persistidos e mostram estado vazio quando não há registros. A interface informa que a instância é local e não homologada, e não apresenta mais usuário, fatura, alerta, processo, vencimento ou evento fictício.

**A aplicação não está pronta para produção real.** A limpeza de exemplos não implementa identidade, autorização, fonte oficial, aprovação administrativa, segurança operacional ou recuperação de dados. Não rotular esta instância como “produção” até que os bloqueios abaixo sejam resolvidos e homologados.

## Conteúdo sintético removido

- Seis faturas com valores, vencimentos, pagamentos, órgãos, processos e percentuais de confiança inventados.
- Três alertas com severidade e horários inventados; também foi removido o contador fixo de alertas.
- Cartões de processo SEI que reutilizavam as faturas fictícias.
- Eventos, atores e horários fictícios na tela de auditoria.
- Perfil fixo “Mariana Gomes”, iniciais, saudação nominal e identificação institucional não autenticada.
- Botões de filtros, cadastro, revisão, ajuda e reconhecimento que apenas mostravam mensagens sem executar a ação prometida.
- Arrays de séries e distribuições sintéticas sem uso e o módulo frontend de dados sintéticos.

## Comportamento atual da interface

- **Dashboard:** usa a rota persistida de valores candidatos. Mantém explícito que são candidatos e que pagamento, saldo e SEI não foram confirmados. A competência mensal é inferida do caminho do arquivo, não de uma fonte oficial.
- **Faturas e Faturas pendentes:** exibem documentos locais e candidatos persistidos. A transição de quarentena para Faturas organiza o fluxo; não representa aprovação institucional, autenticidade ou pagamento.
- **Processos SEI:** consulta `/api/v1/processes`. Os números são registros locais e não são verificados no SEI.
- **Alertas:** consulta `/api/v1/alerts`. Não há geração automática nem ação de reconhecimento habilitada pela tela.
- **Saldos:** não mostra números; informa que a fonte oficial e o mapeamento não estão configurados.
- **Auditoria:** não inventa eventos. Informa que alguns eventos técnicos persistem, mas a consulta completa e a identidade autenticada do responsável não estão disponíveis.
- **Catálogo:** continua sendo uma lista de referência usada pela extração e pelos agrupamentos. A própria API marca esse catálogo como não verificado; ele não deve ser chamado de catálogo oficial.
- **Estado operacional:** “API/banco conectados” e “monitor ativo” indicam apenas conectividade e estado do processo. Não significam autenticação, homologação, integridade de todos os arquivos ou disponibilidade de sistemas institucionais.

## Bloqueadores para produção real

### 1. Identidade e autorização — crítico

Não há autenticação institucional nem autorização por papel/escopo. Rotas de consulta, leitura de PDFs, propostas de correção, transições de workflow e gravação de regras não distinguem usuário, revisor e administrador. CORS ou loopback não substituem autorização. A API não deve ser exposta a uma rede de usuários antes de implementar e testar identidade, papéis e restrições por recurso.

### 2. Revisão não equivale a aprovação — crítico

A liberação da quarentena valida unicidade e preenchimento de candidatos, mas os candidatos permanecem em estado `candidate`; a API ainda não implementa uma decisão autenticada de aceite/rejeição vinculada a revisor. A transição para “Faturas” é somente uma organização local do fluxo. Não pode ser tratada como aceite legal, confirmação financeira, validação SEI ou aprovação de pagamento.

### 3. Monitoramento de arquivos e fonte autorizada — crítico

O monitor requer uma raiz local explícita. O iniciador integrado usa `C:\2026` por padrão e liga o monitor. Nos eventos observados, o código calcula hash, lê o arquivo para extração de conteúdo e grava candidatos; portanto, não é apenas monitoramento de metadados. A fila é local/em memória, o monitor não reconcilia nem faz backfill de arquivos existentes e eventos perdidos podem deixar o índice incompleto. Antes de operação, confirmar formalmente raiz, proprietário, permissões da conta de serviço, tipos de arquivo, volume, retenção, impacto de I/O, tratamento de erros e reconciliação.

### 4. Fontes institucionais ausentes — crítico

- Não há consulta nem validação no SEI.
- Não há fonte oficial de pagamento, saldo ou vencimento.
- Não há planilha oficial de saldos conectada.
- Não há identidade institucional, correio nem notificação.
- Alertas não são calculados automaticamente por regras aprovadas.

Não criar ou inferir esses fatos a partir de valores candidatos ou nomes de pastas.

### 5. Catálogo e regras — alto

Órgãos, serviços, materiais e fornecedores são definidos como listas de referência no código e estão marcados como não verificados. Os rascunhos de exclusividade/rateio persistem, mas não são aplicados aos cálculos nem às extrações e não têm aprovação autenticada. É necessário definir fonte oficial, responsável, versionamento, vigência, justificativa e processo de aprovação.

### 6. Auditoria — alto

A tabela recebe alguns eventos técnicos, mas não há ator autenticado, consulta completa pela interface, controles de imutabilidade ou revisão independente da trilha. Eventos atuais não oferecem não repúdio nem atribuição confiável de responsabilidade.

### 7. Implantação e continuidade — alto

`npm run dev` inicia servidores de desenvolvimento locais; não é pipeline ou comando de implantação de produção. A API permanece em loopback. Não foram definidos TLS, gestão de segredos, política de logs, backup/restore testado, RPO/RTO, alertas operacionais, atualização/rollback, ambiente de homologação ou plano de incidente.

### 8. Migrações e banco — alto

A API usa SQLite se `SIGES_DATABASE_URL` não estiver definida. A conexão PostgreSQL observada no healthcheck prova somente que a consulta simples respondeu. Antes de migrações persistentes, exigir backup testado, revisão/aprovação da migration e ensaio de recuperação. Não executar downgrades em dados de produção.

## Decisões e evidências necessárias para avançar

1. Identidade: provedor, grupos, papéis, escopo por documento e processo de revogação.
2. Revisão: campos obrigatórios por classe de documento, estados aceito/rejeitado, revisor responsável, segunda aprovação quando necessária e evidência obrigatória.
3. Fontes: raiz autorizada, catálogo oficial, SEI, pagamentos e planilha de saldos; indicar proprietários, permissões, frequência e evidência por campo.
4. Regras: exclusividade/rateio, natureza bruto/líquido, componentes monetários, tratamento de divergência e vigência.
5. Segurança/infraestrutura: ambiente de execução, TLS, rede, gestão de segredos, logs, retenção, backup, RPO/RTO e resposta a incidente.
6. Homologação: testes PostgreSQL de integração, autorização negativa/positiva, concorrência, recuperação, reconciliação do monitor, desempenho, vulnerabilidades e aceite do responsável institucional.

## Verificações de desenvolvimento desta limpeza

- Faturas, alertas, usuário e eventos fictícios foram removidos da interface e do dataset frontend.
- Processos e alertas consultam as rotas da API.
- Os avisos remanescentes descrevem limites reais, não conteúdo inventado.
- Build do frontend: concluído; aviso não bloqueante de bundle acima de 500 kB.
- Testes backend: `43 passed`; há um aviso de depreciação relacionado à combinação Starlette/TestClient.
- Healthcheck consultado sem acessar dados de documentos: API `ok`, PostgreSQL conectado, monitor ativo, 0 arquivos processados desde o início e 0 erros.
- A API foi reiniciada após esta verificação e responde `environment=local_unverified`, com PostgreSQL conectado. O monitor está ativo; seu contador reiniciou em zero, pois ele observa eventos futuros e não faz backfill.
