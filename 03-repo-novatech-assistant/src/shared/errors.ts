// Custom errors do projeto NovaTech Assistant.
// Escopo T-01: apenas ValidationError (borda de entrada do endpoint).
// T-03 expande este arquivo com RetrievalError, CompletionError, NoCoverageError.

/** Base para erros do domínio, carregando um statusCode HTTP. */
export abstract class AppError extends Error {
  abstract readonly statusCode: number;

  protected constructor(message: string) {
    super(message);
    this.name = new.target.name;
    // mantém a cadeia de protótipo correta ao estender Error em TS/ESM
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

/** Input do request inválido (falha de validação Zod na borda do endpoint). */
export class ValidationError extends AppError {
  readonly statusCode = 400;
  /** Lista de problemas de validação, legível para o cliente. */
  readonly issues: readonly string[];

  constructor(message: string, issues: readonly string[] = []) {
    super(message);
    this.issues = issues;
  }
}
