// Handler do POST /api/feedback — reescrito conforme o AGENTS.md.
//
// Correções sobre a versão gerada pelo Copilot:
//  - validação com Zod (não `as any`);
//  - logging com o logger estruturado (pino), nunca console.log;
//  - NUNCA loga dados pessoais (attendantEmail é redigido / nunca emitido no log);
//  - imports estáticos no topo (sem require dinâmico);
//  - persistência atrás de uma porta injetável (testável sem Cosmos real).

import { logger } from "../../shared/logger.js";
import { ValidationError } from "../../shared/errors.js";
import { validateFeedbackInput, type FeedbackInput } from "./validator.js";

/** Registro de feedback já validado e pronto para persistir. */
export interface FeedbackRecord extends FeedbackInput {
  readonly timestamp: string;
}

/** Porta de persistência (implementada por um adapter de Cosmos no wire-up Azure). */
export interface FeedbackRepository {
  create(record: FeedbackRecord): Promise<{ id: string }>;
}

/** Resultado do handler, desacoplado do tipo HTTP do Azure. */
export interface HandlerResult {
  readonly status: number;
  readonly body: unknown;
}

/**
 * Núcleo do handler: função pura (recebe body cru + repositório), testável sem HTTP/Azure.
 * Valida, persiste e responde, sem nunca logar dados pessoais.
 */
export async function handleFeedback(
  rawBody: unknown,
  repo: FeedbackRepository,
): Promise<HandlerResult> {
  let input: FeedbackInput;
  try {
    input = validateFeedbackInput(rawBody);
  } catch (err) {
    if (err instanceof ValidationError) {
      // Loga o motivo da rejeição SEM ecoar o corpo (que contém e-mail do atendente).
      logger.warn({ issues: err.issues }, "feedback rejeitado por validação");
      return { status: err.statusCode, body: { error: err.message, issues: err.issues } };
    }
    throw err;
  }

  const record: FeedbackRecord = { ...input, timestamp: new Date().toISOString() };

  try {
    const saved = await repo.create(record);
    // Log de sucesso usa apenas identificadores não-pessoais (queryId, rating). E-mail jamais.
    logger.info({ queryId: record.queryId, rating: record.rating, id: saved.id }, "feedback salvo");
    return { status: 201, body: { id: saved.id } };
  } catch (err) {
    logger.error({ queryId: record.queryId }, "falha ao persistir feedback");
    return { status: 503, body: { error: "Não foi possível registrar o feedback agora." } };
  }
}
