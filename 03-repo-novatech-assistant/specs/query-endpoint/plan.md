# Plan — Query Endpoint

> Fornecido pelo Tech Lead (Cenário 1). Versionado aqui como entrada do SDD.

## Approach
Azure Function HTTP trigger que:
1. Recebe pergunta do atendente via POST /api/query
2. Converte pergunta em embedding via Azure OpenAI
3. Busca top-5 chunks no Azure AI Search
4. Monta prompt com chunks + system prompt + pergunta
   (respeitando context budget: ~4K system + ~8K chunks + pergunta)
5. Envia ao GPT-4o e retorna resposta com source_document

## Technical Decisions
- TypeScript com Azure Functions v4
- Zod para validação de input/output
- Retry com exponential backoff para chamadas Azure
- Structured logging com pino

## Prior Decisions (do cenário 1)
- Context budget definido na ADR-0002: ~4K system + ~8K chunks
- Documentos contraditórios tratados com metadado de vigência (ADR-0003)
- System prompt versionado em /prompts/system-prompt.md

## Dependencies
- Azure AI Search index must be populated (pipeline de ingestão)
- System prompt must be finalized (ver /prompts/system-prompt.md)
