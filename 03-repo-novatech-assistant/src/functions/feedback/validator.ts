// Validação de input do POST /api/feedback. Função pura, testável sem HTTP.
// Convenções: TypeScript strict, Zod, sem `any`, imports estáticos.

import { z } from "zod";
import { ValidationError } from "../../shared/errors.js";

/** Schema do corpo do feedback. `.strict()` rejeita campos desconhecidos. */
export const feedbackInputSchema = z
  .object({
    queryId: z.string().uuid("queryId deve ser um UUID"),
    rating: z.number().int().min(1).max(5),
    comment: z.string().trim().max(2000).optional(),
    attendantEmail: z.string().email("attendantEmail inválido"),
  })
  .strict();

/** Feedback validado e tipado. */
export type FeedbackInput = z.infer<typeof feedbackInputSchema>;

/**
 * Valida o corpo cru do feedback.
 * @throws {ValidationError} quando o input não satisfaz o schema.
 */
export function validateFeedbackInput(raw: unknown): FeedbackInput {
  const result = feedbackInputSchema.safeParse(raw);
  if (!result.success) {
    const issues = result.error.issues.map(
      (i) => `${i.path.join(".") || "(raiz)"}: ${i.message}`,
    );
    throw new ValidationError("Input inválido para /api/feedback", issues);
  }
  return result.data;
}
