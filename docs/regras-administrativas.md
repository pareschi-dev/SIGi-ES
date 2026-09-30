# Regras administrativas — desenho inicial

## Escopo da tela

A seção apresenta um cartão para cada fornecedor e cada material do catálogo de referência. A identidade da regra é o par `(tipo, id do catálogo)`, evitando colisões quando fornecedor e material compartilham o mesmo número. As regras salvas são rascunhos versionados e cada mudança gera um evento de auditoria.

## Campos propostos por regra

- **Tipo de cobrança:** não classificada, exclusiva ou rateio.
- **Critério de rateio:** não definido, partes iguais, percentuais contratuais, consumo/medição ou valor manual. A opção inicial e a única segura sem evidência é “não definido”.
- **Natureza do valor da fatura:** não definida, bruta ou líquida.
- **Natureza do valor do termo de recebimento:** não definida, bruta ou líquida.
- **Divergência:** manter os valores separados e encaminhar à revisão humana; não definir precedência, tolerância monetária, saldo ou pagamento automaticamente.
- **Justificativa:** obrigatória para registrar uma nova versão.

## Extração e apresentação

`invoice_amount_brl` e `reimbursement_term_amount_brl` continuam sendo candidatos distintos, com evidência própria. A interface os apresenta em linhas separadas. Se ambos existirem e forem diferentes, ou houver conflito entre as naturezas bruto/líquido, o cartão sinaliza a divergência. Valores ausentes ou múltiplos permanecem ausentes/ambíguos; não são completados por inferência.

A regra de rateio é apenas um rascunho administrativo: nenhum rateio por órgão, serviço, unidade, percentual ou consumo será calculado nesta etapa. A classificação exclusiva também não confirma que uma cobrança pertence a um único órgão.

## Limites e decisões pendentes

- O catálogo de fornecedores/materiais é referência fornecida pelo usuário e ainda não verificada.
- Não há autenticação ou autorização administrativa implementada; não publicar esta edição em ambiente compartilhado/produção antes de definir identidade, papéis e escopo.
- Ainda faltam contrato/documento que comprove o tipo de cobrança, critério oficial de rateio, definição institucional de bruto/líquido por fonte e tratamento aprovado de divergências.
- A revisão humana continua obrigatória; rascunhos não alteram PDFs, candidatos, dashboard financeiro nem estados de pagamento.
