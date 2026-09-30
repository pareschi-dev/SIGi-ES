# Ingestão histórica da cópia local 2026

## Inventário realizado

Em 27/09/2026, inventário somente de metadados da raiz local resultou em:

- 1.014 arquivos; 1.320.529.137 bytes no total.
- 951 PDF, 44 XLS, 15 XLSX, 2 XLSM e 2 arquivos sem extensão.
- 54 grupos de diretório (prefixos até profundidade 3), profundidade máxima 4, nenhum erro de stat no inventário.

A enumeração não leu o conteúdo dos arquivos. Nomes de pastas e fornecedores são pistas estruturais, não catálogo oficial de órgãos ou serviços. A cópia inclui estruturas como `EXECUTADO & PROGRAMADO`, `RATEIO`, `MATERIAL` e `SERVIÇO`, além de vários prestadores locais.

## Ingestão planejada/implementada

`backend/app/ingest_local_copy.py` processa uma raiz explicitamente autorizada. O script operacional é `backend/ingest-local-copy.ps1`; valida conexão, verifica schema, executa migrações pendentes e solicita senha com entrada oculta. A ingestão somente deve rodar depois de parar temporariamente o servidor API que usa a mesma role PostgreSQL (uma role normalmente permite uma conexão simultânea por vez conforme suas configurações). Rodar da mesma forma que o monitor: raiz absoluta `C:\2026`.

- Guarda hash SHA-256, tamanho, MIME e caminho relativo. Não persiste caminho absoluto nem conteúdo do arquivo.
- Extrai candidato SEI com formato reconhecido, valor `R$`, vencimento rotulado, campos em células/linhas e pistas do caminho da pasta.
- PDF nativo, XLS/XLSX/XLSM, CSV e DOCX são processáveis; OCR não existe. `.xls` expõe valores em cache e não é possível garantir aqui que uma célula veio de fórmula; cada candidato XLS traz método que declara essa incerteza.
- Formatos sem parser ainda podem ser registrados como documento com aviso de revisão.
- Todo valor é `candidate`, confidence nula; nenhuma fatura/processo é confirmada, não há classificação paga, saldo oficial ou validação SEI.
- A execução é idempotente em hash+caminho e candidatos; preserva arquivos originais.
- Limites atuais: 100 MiB por arquivo, 500 páginas PDF, 50.000 células e limites de pacote Office definidos no parser.

## Visualização

A página **Documentos importados** apresenta contagens, extensões, pistas de diretórios e uma página de candidatos com arquivo relativo, campo, valor original/normalizado e localização da evidência. Os registros não serão mesclados automaticamente às faturas demonstrativas já exibidas no dashboard.

## Segurança operacional

Não fazer screenshots/exports públicos com nomes/caminhos ou valores financeiros. Manter a API apenas em loopback até existir autenticação. Uma cópia local pode conter informações pessoais/financeiras: acesso e retenção devem seguir a política da organização. A aprovação humana e calibração precisam preceder qualquer uso decisório.
