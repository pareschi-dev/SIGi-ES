# Ingestão segura — primeira fatia da Etapa 3

O módulo `backend/app/scanner.py` implementa descoberta e indexação de metadados, sem extrair conteúdo dos arquivos.

## Comportamento

- A função exige que o chamador passe uma raiz existente; não há caminho padrão para `C:\2026`.
- Somente extensões permitidas são consideradas (`.pdf`, `.xlsx`, `.xlsm`, `.docx`, `.xml`, `.csv`); extensão não comprova o formato real do conteúdo.
- A varredura não segue diretórios simbólicos, não lê arquivos por links simbólicos e confirma que cada caminho resolvido permanece dentro da raiz.
- Tamanho máximo é configurável; arquivos acima do limite são reportados sem serem lidos.
- Hash SHA-256 é calculado em blocos de 1 MiB, em modo binário de leitura. Mudança de tamanho ou mtime durante leitura é reportada como erro recuperável.
- O relatório contém caminho relativo, nome, hash, tamanho e MIME inferido. Não guarda caminho absoluto nem trecho do documento.
- `index_scan_report()` usa fonte + caminho relativo + hash como chave de idempotência. Alteração do conteúdo no mesmo caminho cria novo registro para preservar a versão anterior.
- Issues são representadas sem path absoluto. Arquivos originais não são movidos, renomeados, apagados ou modificados.

## Uso em desenvolvimento

Importe `scan_directory` e forneça uma pasta temporária de teste ou uma raiz institucional cuja autorização já tenha sido aprovada. O módulo ainda não oferece comando CLI, scheduler, watchdog, API para disparar scan, espera de estabilidade do arquivo, extração PDF/OCR, regras por pasta ou fluxo UI de revisão.

Não execute sobre diretórios reais sem validar a autorização, o impacto de I/O, os limites de volume e as permissões da conta de serviço. O código não valida autenticidade do SEI nem classifica pagamento.
