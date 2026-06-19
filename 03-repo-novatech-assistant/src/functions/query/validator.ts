// Validação determinística do input do POST /api/query.
// Task T-01 (SDD). Função pura, sem dependência do HTTP trigger nem de serviços Azure,
// para ser testável isoladamente. Padrões: TypeScript strict, Zod, sem `any`, sem console.log.

import { z } from "zod";
import { ValidationError } from "../../shared/errors.js";

/**
 * Limite de turnos no histórico.
 * Origem: ADR-0002 (context budget) — histórico limitado a 3 turnos por query.
 */
export const MAX_HISTORY_TURNS = 3;

/** Comprimento máximo da pergunta do atendente (proteção de budget e abuso). */
export const MAX_QUESTION_LENGTH = 2000;

/** Um turno do histórico de conversa (pergunta do atendente + resposta do assistente). */
const historyTurnSchema = z
  .object({
    question: z.string().trim().min(1).max(MAX_QUESTION_LENGTH),
    answer: z.string().trim().min(1),
  })
  .strict();

/**
 * Schema do corpo do request. `.strict()` rejeita campos desconhecidos
 * (não propaga input não declarado para dentro do pipeline).
 */
export const queryInputSchema = z
  .object({
    question: z
      .string({ required_error: "question é obrigatória" })
      .trim()
      .min(1, "question não pode ser vazia")
      .max(MAX_QUESTION_LENGTH, `question excede ${MAX_QUESTION_LENGTH} caracteres`),
    conversationId: z.string().uuid("conversationId deve ser um UUID").optional(),
    history: z
      .array(historyTurnSchema)
      .max(MAX_HISTORY_TURNS, `history excede ${MAX_HISTORY_TURNS} turnos (ADR-0002)`)
      .optional(),
  })
  .strict();

/** Input já validado e tipado do query endpoint. */
export type QueryInput = z.infer<typeof queryInputSchema>;

/**
 * Valida o input cru do request.
 * @throws {ValidationError} quando o input não satisfaz o schema.
 */
export function validateQueryInput(raw: unknown): QueryInput {
  const result = queryInputSchema.safeParse(raw);
  if (!result.success) {
    const issues = result.error.issues.map(
      (i) => `${i.path.join(".") || "(raiz)"}: ${i.message}`,
    );
    throw new ValidationError("Input inválido para /api/query", issues);
  }
  return result.data;
}
