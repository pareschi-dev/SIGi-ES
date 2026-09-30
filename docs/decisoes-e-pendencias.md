# Decisões, hipóteses e pendências

## Confirmado nesta etapa
- Nome do produto: SIG-ES.
- Público e domínio pretendidos: gestão administrativa de faturas e processos relacionados ao SEI.
- Interface em português brasileiro.
- O workspace estava vazio no início do trabalho.

## Hipóteses técnicas provisórias
- Frontend React, TypeScript e Vite.
- Backend Python com FastAPI.
- Dados de demonstração puramente sintéticos.
- Prototipação sem persistência, sem login real e sem integrações externas.

Essas escolhas podem mudar após confirmar ambiente institucional, requisitos de implantação, identidade e segurança.

## Não implementado / não confirmado
- Acesso autorizado a `C:\2026` e à pasta de rede.
- API ou credenciais do SEI.
- Conteúdo, cabeçalhos e semântica da planilha de saldos.
- Fonte oficial que confirma pagamento.
- Catálogo de órgãos, serviços, pastas e critérios de rateio.
- Provedor de identidade, papéis detalhados e escopo de acesso.
- Regras de retenção, auditoria, LGPD e disponibilidade.

## Decisões de segurança
- Ingestão futura deverá começar em leitura somente e preservar arquivos originais.
- Dados extraídos serão candidatos com origem por campo e revisão humana; não serão fatos oficiais por inferência.
- Indisponibilidade de uma fonte deverá ser visível; não se reutilizará um saldo antigo como se fosse atual.
- Números exibidos nesta etapa são fictícios e indicados no banner de demonstração.
