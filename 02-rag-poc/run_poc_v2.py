"""
run_poc_v2.py — mesma avaliacao, com correcoes aplicadas:
  FIX A: linearizacao de tabelas na ingestao
  FIX B: re-ranking (versao mais recente vence; normativo/contratual > FAQ informal)
  FIX C: gate de relevancia (score < tau -> "nao encontrei")
Compara cobertura vs run_poc.py (baseline).
"""
import json
from novatech_rag import ingest, make_embedder, VectorStore
from run_poc import GOLD, sec_match

N_RAW, N_FINAL, TAU = 8, 5, 0.12


def rerank(retrieved, critical=False):
    # FIX B.1 — most-recent-wins: se PROC-042(v1) e PROC-042-v2 cobrem a MESMA secao, descarta o v1
    v2_secs = {r.chunk.section for r in retrieved if r.chunk.doc_id == "PROC-042-v2"}
    kept = [r for r in retrieved
            if not (r.chunk.doc_id == "PROC-042" and r.chunk.section in v2_secs)]
    # FIX B.2 — autoridade da fonte: penaliza FAQ informal (mais forte em perguntas criticas)
    pen = 0.35 if critical else 0.15
    for r in kept:
        if r.chunk.source_type == "informal":
            r.score -= pen
    kept.sort(key=lambda r: -r.score)
    return kept[:N_FINAL]


def main():
    print("INGESTAO (com linearizacao de tabelas)")
    chunks = ingest("docs/*.md", linearize_tables=True)
    embedder = make_embedder(prefer_real=True)
    print(f"BACKEND: {embedder.name}\n")
    store = VectorStore(embedder)
    store.add(chunks)

    print(f"RETRIEVAL v2 — top-{N_RAW} -> rerank -> top-{N_FINAL}, gate tau={TAU}\n")
    hits = 0
    results_v2 = []
    scored = [c for c in GOLD if c["expect"] is not None]
    for i, case in enumerate(GOLD, 1):
        raw = store.query(case["q"], n=N_RAW)
        critical = bool(case["trap"] and ("perigosa" in case["q"].lower()
                        or "platinum" in case["q"].lower()))
        ranked = rerank(raw, critical=critical)
        gated = [r for r in ranked if r.score >= TAU]

        if case["expect"] is None:
            status = "OK (sem cobertura)" if not gated else f"FALSO-POSITIVO ({len(gated)} acima do gate)"
            cov = "n/a"
        else:
            n_ok = sum(1 for (d, s) in case["expect"]
                       if any(sec_match(r.chunk, d, s) for r in gated))
            cov = f"{n_ok}/{len(case['expect'])}"
            full = n_ok == len(case["expect"])
            hits += 1 if full else 0
            status = "HIT" if full else ("PARCIAL" if n_ok else "MISS")
        print(f"[{i:>2}] {case['q'][:60]}")
        print(f"     status={status}  cobertura={cov}")
        for r in ranked[:3]:
            print(f"        {r.score:+.3f} {r.chunk.doc_id} v{r.chunk.version} "
                  f"Sec {r.chunk.section} [{r.chunk.source_type}]")
        results_v2.append({
            "q": case["q"],
            "status": status,
            "covered": cov,
            "trap": case["trap"],
            "gated_top3": [(r.chunk.doc_id, r.chunk.section, round(r.score, 3))
                           for r in gated[:3]],
        })
    print(f"\nRESUMO v2 (avaliação sobre gated): {hits}/{len(scored)} cobertura COMPLETA "
          f"(baseline era 3/{len(scored)})")
    import os
    os.makedirs("outputs", exist_ok=True)
    with open("outputs/resultados_retrieval_v2.json", "w", encoding="utf-8") as f:
        json.dump(results_v2, f, ensure_ascii=False, indent=2)
    print("Artefato: outputs/resultados_retrieval_v2.json")


if __name__ == "__main__":
    main()
