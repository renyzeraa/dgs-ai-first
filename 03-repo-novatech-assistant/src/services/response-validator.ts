// Harness de código (Cenário 3, Ex 3.1) — structured output + verificações determinísticas.
//
// O prompt do modelo é PROBABILÍSTICO: pede para responder em JSON e citar a fonte, mas não
// garante. Este módulo é DETERMINÍSTICO: rejeita programaticamente qualquer resposta que não
// satisfaça o schema ou que viole os guardrails. É a rede de segurança que não depende de o
// modelo "lembrar" de fazer a coisa certa.

import { z } from "zod";
import { logger } from "../shared/logger.js";

/** Resposta padrão segura devolvida quando a resposta do modelo é rejeitada. */
export const SAFE_FALLBACK_ANSWER =
  "Não encontrei essa informação de forma confiável na documentação disponível. " +
  "Sugiro escalar ao supervisor.";

/**
 * Schema do structured output que o modelo DEVE seguir.
 * `.strict()` rejeita campos extras (o modelo não pode contrabandear chaves não previstas).
 */
export const assistantResponseSchema = z
  .object({
    answer: z.string().trim().min(1, "answer não pode ser vazia"),
    source_document: z
      .string()
      .trim()
      .min(1, "source_document é obrigatório")
      .nullable(),
    confidence_score: z.number().min(0).max(1),
  })
  .strict();

/** Tipo inferido do structured output válido. */
export type AssistantResponse = z.infer<typeof assistantResponseSchema>;

/** Resultado da validação: aprovado (com a resposta) ou rejeitado (com motivo + fallback). */
export type ValidationOutcome =
  | { ok: true; response: AssistantResponse }
  | { ok: false; reason: string; response: AssistantResponse };

/** Constrói a resposta de fallback segura, sempre com confiança 0 e sem fonte. */
function safeFallback(): AssistantResponse {
  return { answer: SAFE_FALLBACK_ANSWER, source_document: null, confidence_score: 0 };
}

/**
 * Guardrail 2 (determinístico): se a resposta trata de DEVOLUÇÃO de CARGA PERIGOSA, ela DEVE
 * conter a negativa. Se afirmar que a devolução é possível, é bloqueada.
 *
 * Regra de negócio: POL-001 §3.2 — cargas perigosas (classes 1-6 ANTT) NÃO são elegíveis para
 * devolução pelo processo padrão. O modelo às vezes inverte a regra (armadilha 4 do Anexo B).
 *
 * Cobertura de variações: normaliza acentos/caixa e detecta família de termos de devolução e
 * de carga perigosa, além de marcadores de afirmação ("pode", "é possível", "sim").
 */
function violatesDangerousGoodsReturnRule(answer: string): boolean {
  const norm = answer
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "") // remove acentos
    .toLowerCase();

  const mentionsDangerous = /\bcarga(s)?\s+perigosa(s)?\b/.test(norm);
  const mentionsReturn = /\b(devolu|devolv)\w*/.test(norm); // devolução, devolver, devolve...
  if (!mentionsDangerous || !mentionsReturn) return false;

  // Há negativa explícita? (nao pode, nao e possivel, nao sao elegiveis, nao permitido...)
  const hasNegation =
    /\bnao\b[\s\w,]{0,40}\b(pode|podem|e possivel|sao elegiveis|elegivel|permitid|aceit)/.test(norm) ||
    /\bnao\s+e\s+possivel\b/.test(norm) ||
    /\bnao\s+pode\b/.test(norm);

  // A negativa tem PRIORIDADE: se a resposta nega a devolução, está correta — mesmo que
  // contenha as palavras "podem ser devolvidas" dentro de uma construção negativa
  // ("não podem ser devolvidas"). Sem esta prioridade, uma resposta correta seria
  // bloqueada por falso positivo (ver code review, problema #2).
  if (hasNegation) return false;

  // Sem negativa: qualquer menção a devolução de carga perigosa é tratada como violação,
  // afirme explicitamente ou apenas omita a negativa exigida.
  return true;
}

/**
 * Valida a resposta crua do modelo contra o schema e aplica os 2 guardrails determinísticos.
 * Em QUALQUER falha: registra o motivo (logger, sem dados sensíveis) e retorna o fallback seguro.
 *
 * @param raw resposta crua do modelo (deveria ser o JSON do structured output)
 */
export function validateAssistantResponse(raw: unknown): ValidationOutcome {
  // Camada 1 — schema (structured output)
  const parsed = assistantResponseSchema.safeParse(raw);
  if (!parsed.success) {
    const reason =
      "schema_invalido: " +
      parsed.error.issues.map((i) => `${i.path.join(".") || "(raiz)"}: ${i.message}`).join("; ");
    logger.warn({ reason }, "resposta rejeitada pelo harness");
    return { ok: false, reason, response: safeFallback() };
  }
  const response = parsed.data;

  // Guardrail 1 — source_document obrigatório (não pode ser nulo/vazio na resposta final)
  if (response.source_document === null || response.source_document.trim() === "") {
    const reason = "guardrail_source_document_ausente";
    logger.warn({ reason }, "resposta rejeitada pelo harness");
    return { ok: false, reason, response: safeFallback() };
  }

  // Guardrail 2 — devolução de carga perigosa sem a negativa exigida
  if (violatesDangerousGoodsReturnRule(response.answer)) {
    const reason = "guardrail_carga_perigosa_devolucao";
    logger.warn({ reason }, "resposta bloqueada pelo harness");
    return { ok: false, reason, response: safeFallback() };
  }

  return { ok: true, response };
}
