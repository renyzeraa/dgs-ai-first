import { describe, it, expect } from "vitest";
import {
  validateQueryInput,
  MAX_HISTORY_TURNS,
  MAX_QUESTION_LENGTH,
} from "../../src/functions/query/validator.js";
import { ValidationError } from "../../src/shared/errors.js";

describe("validateQueryInput", () => {
  it("should return a typed object when given a minimal valid request", () => {
    // arrange
    const raw = { question: "Qual o SLA do cliente Gold?" };
    // act
    const result = validateQueryInput(raw);
    // assert
    expect(result.question).toBe("Qual o SLA do cliente Gold?");
    expect(result.conversationId).toBeUndefined();
    expect(result.history).toBeUndefined();
  });

  it("should trim surrounding whitespace when question has padding", () => {
    // arrange
    const raw = { question: "   prazo de devolução?   " };
    // act
    const result = validateQueryInput(raw);
    // assert
    expect(result.question).toBe("prazo de devolução?");
  });

  it("should throw ValidationError when question is missing", () => {
    // arrange
    const raw = {};
    // act + assert
    expect(() => validateQueryInput(raw)).toThrow(ValidationError);
  });

  it("should throw ValidationError when question is empty after trim", () => {
    // arrange
    const raw = { question: "     " };
    // act + assert
    expect(() => validateQueryInput(raw)).toThrow(ValidationError);
  });

  it("should throw ValidationError when question exceeds the max length", () => {
    // arrange
    const raw = { question: "a".repeat(MAX_QUESTION_LENGTH + 1) };
    // act + assert
    expect(() => validateQueryInput(raw)).toThrow(ValidationError);
  });

  it("should accept a valid UUID conversationId when present", () => {
    // arrange
    const raw = {
      question: "Posso devolver carga perigosa?",
      conversationId: "3f2504e0-4f89-41d3-9a0c-0305e82c3301",
    };
    // act
    const result = validateQueryInput(raw);
    // assert
    expect(result.conversationId).toBe("3f2504e0-4f89-41d3-9a0c-0305e82c3301");
  });

  it("should throw ValidationError when conversationId is not a UUID", () => {
    // arrange
    const raw = { question: "ok?", conversationId: "not-a-uuid" };
    // act + assert
    expect(() => validateQueryInput(raw)).toThrow(ValidationError);
  });

  it(`should accept history with exactly ${MAX_HISTORY_TURNS} turns`, () => {
    // arrange
    const turn = { question: "q", answer: "a" };
    const raw = { question: "nova pergunta", history: Array(MAX_HISTORY_TURNS).fill(turn) };
    // act
    const result = validateQueryInput(raw);
    // assert
    expect(result.history).toHaveLength(MAX_HISTORY_TURNS);
  });

  it(`should throw ValidationError when history exceeds ${MAX_HISTORY_TURNS} turns (ADR-0002)`, () => {
    // arrange
    const turn = { question: "q", answer: "a" };
    const raw = { question: "nova", history: Array(MAX_HISTORY_TURNS + 1).fill(turn) };
    // act + assert
    expect(() => validateQueryInput(raw)).toThrow(ValidationError);
  });

  it("should strip unknown fields when input has extra keys", () => {
    // arrange
    const raw = { question: "ok?", isAdmin: true, debug: "x" } as Record<string, unknown>;
    // act + assert — strict() rejeita chaves desconhecidas
    expect(() => validateQueryInput(raw)).toThrow(ValidationError);
  });

  it("should expose human-readable issues on the thrown ValidationError", () => {
    // arrange
    const raw = { question: "" };
    // act
    let caught: unknown;
    try {
      validateQueryInput(raw);
    } catch (e) {
      caught = e;
    }
    // assert
    expect(caught).toBeInstanceOf(ValidationError);
    const err = caught as ValidationError;
    expect(err.statusCode).toBe(400);
    expect(err.issues.length).toBeGreaterThan(0);
  });
});
