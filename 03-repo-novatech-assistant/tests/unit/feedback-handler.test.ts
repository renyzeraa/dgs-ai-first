import { describe, it, expect, vi } from "vitest";
import { handleFeedback, type FeedbackRepository } from "../../src/functions/feedback/handler.js";

const validBody = {
  queryId: "3f2504e0-4f89-41d3-9a0c-0305e82c3301",
  rating: 5,
  comment: "ótimo",
  attendantEmail: "atendente@novatech.com.br",
};

function repoOk(): FeedbackRepository {
  return { create: vi.fn().mockResolvedValue({ id: "abc-123" }) };
}

describe("handleFeedback", () => {
  it("should persist and return 201 with id when input is valid", async () => {
    // arrange
    const repo = repoOk();
    // act
    const res = await handleFeedback(validBody, repo);
    // assert
    expect(res.status).toBe(201);
    expect(res.body).toEqual({ id: "abc-123" });
    expect(repo.create).toHaveBeenCalledOnce();
  });

  it("should return 400 and not call the repo when input is invalid", async () => {
    // arrange
    const repo = repoOk();
    const bad = { queryId: "not-uuid", rating: 9, attendantEmail: "x" };
    // act
    const res = await handleFeedback(bad, repo);
    // assert
    expect(res.status).toBe(400);
    expect(repo.create).not.toHaveBeenCalled();
  });

  it("should return 503 when persistence fails", async () => {
    // arrange
    const repo: FeedbackRepository = { create: vi.fn().mockRejectedValue(new Error("cosmos down")) };
    // act
    const res = await handleFeedback(validBody, repo);
    // assert
    expect(res.status).toBe(503);
  });

  it("should NEVER write the attendant email to logs", async () => {
    // arrange — captura tudo que vai para stderr (onde o logger estruturado escreve)
    const written: string[] = [];
    const spy = vi.spyOn(process.stderr, "write").mockImplementation((chunk: unknown) => {
      written.push(String(chunk));
      return true;
    });
    // act
    await handleFeedback(validBody, repoOk());
    spy.mockRestore();
    // assert — o e-mail do atendente não aparece em nenhuma linha de log
    const allLogs = written.join("\n");
    expect(allLogs).not.toContain("atendente@novatech.com.br");
    expect(allLogs).not.toContain("@novatech");
  });
});
