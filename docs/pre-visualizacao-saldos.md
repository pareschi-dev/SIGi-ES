# Pré-visualização configurável de planilha — Etapa 5

`backend/app/balance_preview.py` lê XLSX/XLSM localmente e cria uma prévia em memória. O usuário do código precisa fornecer `WorkbookMapping` com nome exato da aba, linha de cabeçalho, colunas para organização, competência e saldo, e formato explícito de competência. Referências de coluna podem ser letras (A, B, C) ou cabeçalhos únicos.

## Proteções e resultado

- Sem caminho, planilha, aba, coluna ou formato padrão; nada aponta para um compartilhamento real.
- Modo `read_only`, fórmulas não são executadas nem lidas como valores, macros não são executadas e o workbook nunca é salvo.
- Validação da planilha/aba/mapeamento, limite de arquivo, limite de linhas, limites do pacote Office e hash SHA-256 da fonte.
- Valores normalizados para `Decimal` com até duas casas; períodos convertidos para o primeiro dia do mês.
- Linhas válidas ficam como candidatos de prévia; linhas inválidas têm códigos de rejeição sem copiar valores financeiros para mensagens.
- Cada registro válido aponta para as células originais. O relatório não é persistido nem transforma saldo em fato oficial.

## Não implementado

Ainda não há leitura de caminho de rede, agendamento, retry por arquivo bloqueado, tabela de importações/snapshots, mapeamento de sigla a cadastro oficial, interface de configuração, comparação com faturas, cálculo de saldo projetado ou geração de alertas. Tudo depende de amostra aprovada e semântica confirmada pelo responsável.
