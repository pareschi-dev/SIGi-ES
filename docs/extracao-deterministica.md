# Extração documental determinística — Etapa 4

## Escopo atual

O módulo `backend/app/extractor.py` lê localmente PDF com texto nativo, XLSX/XLSM e DOCX. Produz somente candidatos para revisão posterior; não confirma valores, pagamento, autenticidade ou existência de processos.

- Processo: extrai strings no formato visual `NNNNN.NNNNNN/AAAA-NN`; isso não é validação SEI.
- Valor: candidato com prefixo monetário `R$` e padrão brasileiro de centavos, normalizado como decimal textual. Quando o contexto local identifica uma fatura, classifica como `invoice_amount_brl`; quando identifica termo de recebimento/atesto, como `reimbursement_term_amount_brl`; sem evidência suficiente, conserva `amount_brl` genérico.
- Precedência para comparação/revisão: candidatos de `reimbursement_term_amount_brl` vêm antes de candidatos da fatura. Se houver mais de um valor no termo, todos permanecem candidatos e nenhum é escolhido automaticamente.
- Catálogo: reconhece órgão, material, serviço e fornecedor fornecidos pelo usuário e registra o ID de referência como valor normalizado; o texto original e a página/célula continuam disponíveis como evidência. O catálogo não foi verificado externamente.
- Vencimento: somente datas precedidas por rótulo reconhecido e validadas como data de calendário.
- Confiança fica nula; não existe score calibrado.
- Evidência aponta página PDF, célula/aba ou parágrafo/célula de tabela DOCX.
- A persistência idempotente conserva os candidatos em estado `candidate`, sem promovê-los para fatura/processo confirmados.

## Limites e proteções

- Limite padrão do arquivo: 100 MiB.
- PDF: até 500 páginas; sem OCR. PDFs protegidos por senha são recusados para tratamento manual autorizado.
- Planilha: modo `read_only`, fórmulas não calculadas nem usadas, limite padrão de 50.000 células e 100 abas.
- Arquivos Office: validação de arquivo ZIP, quantidade de membros, tamanho descompactado e razão máxima de compressão antes da leitura.
- XLSM nunca é salvo; macros não são executadas.
- Texto bruto integral não é persistido pelo parser.
- Extensão e MIME não comprovam que o documento é legítimo. O parser não consulta rede nem chama modelos de IA.

## Não implementado

OCR, verificação de assinatura/autenticidade, extração de CNPJ/número de fatura, classificação para layouts sem rótulo próximo, confirmação automática de valores, revisão autenticada/auditada e regras por diretório ainda dependem de decisão e amostras anonimizadas aprovadas.

Os testes usam documentos sintéticos criados durante a execução. A ingestão histórica local é uma etapa separada e preserva os originais; seus valores continuam candidatos até revisão.
