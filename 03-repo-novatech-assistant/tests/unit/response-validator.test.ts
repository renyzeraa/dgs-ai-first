import { describe, it, expect } from "vitest";
import {
  validateAssistantResponse,
  assistantResponseSchema,
  SAFE_FALLBACK_ANSWER,
} from "../../src/services/response-validator.js";

describe("assistantResponseSchema", () => {
  it("should accept a well-formed structured output when all fields are valid", () => {
    // arrange
    const raw = { answer: "Prazo de 7 dias úteis.", source_document: "POL-001", confidence_score: 0.9 };
    // act
    const parsed = assistantResponseSchema.safeParse(raw);
    // assert
    expect(parsed.success).toBe(true);
  });

  it("should reject unknown extra fields when the model smuggles a key", () => {
    // arrange
    const raw = { answer: "x", source_document: "POL-001", confidence_score: 0.5, injected: true };
    // act
    const parsed = assistantResponseSchema.safeParse(raw);
    // assert
    expect(parsed.success).toBe(false);
  });

  it("should reject confidence_score out of the 0..1 range", () => {
    // arrange
    const raw = { answer: "x", source_document: "POL-001", confidence_score: 1.4 };
    // act + assert
    expect(assistantResponseSchema.safeParse(raw).success).toBe(false);
  });
});

describe("validateAssistantResponse", () => {
  it("should pass through a valid response when schema and guardrails are satisfied", () => {
    // arrange
    const raw = { answer: "SLA Gold: resolução em 24h.", source_document: "SLA-2024", confidence_score: 0.95 };
    // act
    const outcome = validateAssistantResponse(raw);
    // assert
    expect(outcome.ok).toBe(true);
    if (outcome.ok) expect(outcome.response.source_document).toBe("SLA-2024");
  });

  it("should reject and return safe fallback when input does not match the schema", () => {
    // arrange
    const raw = { answer: "sem score nem fonte" };
    // act
    const outcome = validateAssistantResponse(raw);
    // assert
    expect(outcome.ok).toBe(false);
    expect(outcome.response.answer).toBe(SAFE_FALLBACK_ANSWER);
    expect(outcome.response.confidence_score).toBe(0);
  });

  it("should BLOCK (not just log) when source_document is null", () => {
    // arrange
    const raw = { answer: "Resposta sem fonte.", source_document: null, confidence_score: 0.8 };
    // act
    const outcome = validateAssistantResponse(raw);
    // assert
    expect(outcome.ok).toBe(false);
    if (!outcome.ok) expect(outcome.reason).toContain("source_document");
    expect(outcome.response.answer).toBe(SAFE_FALLBACK_ANSWER);
  });

  it("should BLOCK when source_document is an empty/whitespace string", () => {
    // arrange
    const raw = { answer: "Resposta.", source_document: "   ", confidence_score: 0.8 };
    // act + assert
    expect(validateAssistantResponse(raw).ok).toBe(false);
  });

  it("should BLOCK when answer inverts the dangerous-goods return rule (says it is allowed)", () => {
    // arrange — inversão da regra POL-001 §3.2 (armadilha 4 do Anexo B)
    const raw = {
      answer: "Sim, carga perigosa pode ser devolvida pelo processo padrão.",
      source_document: "POL-001",
      confidence_score: 0.9,
    };
    // act
    const outcome = validateAssistantResponse(raw);
    // assert
    expect(outcome.ok).toBe(false);
    if (!outcome.ok) expect(outcome.reason).toContain("carga_perigosa");
  });

  it("should BLOCK dangerous-goods+return even without accents or with mixed case", () => {
    // arrange — variação: sem acento, caixa mista
    const raw = {
      answer: "CARGA PERIGOSA pode ser DEVOLVIDA normalmente.",
      source_document: "POL-001",
      confidence_score: 0.9,
    };
    // act + assert
    expect(validateAssistantResponse(raw).ok).toBe(false);
  });

  it("should ALLOW the correct dangerous-goods answer that contains the negative", () => {
    // arrange — resposta correta: contém a negativa
    const raw = {
      answer:
        "Não. Cargas perigosas (classes 1 a 6 da ANTT) não podem ser devolvidas pelo processo padrão; escale ao supervisor.",
      source_document: "POL-001",
      confidence_score: 0.92,
    };
    // act
    const outcome = validateAssistantResponse(raw);
    // assert
    expect(outcome.ok).toBe(true);
  });

  it("should NOT trigger the dangerous-goods guardrail for unrelated answers", () => {
    // arrange — fala de devolução comum, sem carga perigosa
    const raw = {
      answer: "O prazo de devolução é de 7 dias úteis após o recebimento.",
      source_document: "POL-001",
      confidence_score: 0.9,
    };
    // act + assert
    expect(validateAssistantResponse(raw).ok).toBe(true);
  });
});
