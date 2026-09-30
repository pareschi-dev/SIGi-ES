# Monitoramento da cópia local

## Escopo configurado

O observador pode ser iniciado explicitamente com `-MonitorRoot 'C:\2026'` no script `backend/run-local.ps1`. Sem esse parâmetro, monitoramento permanece desabilitado. A raiz não é gravada no banco nem retornada pela API.

## O que faz

- Usa eventos do sistema de arquivos do Windows para detectar criação, alteração e movimentação de arquivos permitidos.
- Observa `.pdf`, `.xlsx`, `.xlsm`, `.docx`, `.xml` e `.csv`.
- Aguarda estabilidade do tamanho/timestamps; ignora arquivos removidos, inacessíveis, simbólicos, fora da raiz ou maiores que 100 MiB.
- Lê os bytes somente para calcular SHA-256 e grava no PostgreSQL metadados, caminho relativo, tipo inferido e hash. Não armazena conteúdo do arquivo.
- Preserva arquivos originais: não renomeia, move, apaga nem edita.
- A API de estado mostra contadores e chave lógica da fonte, nunca o caminho absoluto.

## Limites atuais

- Monitoramento é somente de eventos após a inicialização. Não faz varredura histórica completa: os documentos que já estavam em `C:\2026` não são indexados automaticamente.
- Ainda não há reconciliação periódica; eventos do sistema operacional podem ser perdidos. Reiniciar ou indisponibilizar o monitor não produz backfill automático.
- A extração do conteúdo, OCR, classificação, vínculos SEI, alertas financeiros e confirmação humana permanecem desativados.
- A API ainda não tem autenticação; por segurança o script local a vincula somente a `127.0.0.1`. Não a exponha à rede.
- Um evento de arquivo significa apenas que seus metadados foram observados; não valida conteúdo, fatura ou processo.

## Execução local

Use `backend/run-local.ps1` passando `-MonitorRoot 'C:\2026'`. O script solicita a senha PostgreSQL com entrada oculta, confere a conexão e o schema, aplica migrações pendentes e inicia a API. O frontend local em `http://127.0.0.1:5173/` consulta o endpoint de estado do monitor pelo proxy Vite.
