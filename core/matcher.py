import os
import time
import json
import uuid
import logging
import numpy as np
import requests
from sentence_transformers import SentenceTransformer
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger(__name__)

EMBED_MODEL = "BAAI/bge-large-en-v1.5"
LLM_MODEL = "google/gemini-2.5-flash"
TOP_K = 8
VALIDATION_SYSTEM = """You are a matching validator for a marketplace platform.
Given a user query and a list of candidate agents/listings, evaluate each one.
Return a JSON array. Each element must have:
  - id: the agent/listing id
  - match: true or false
  - score: float 0.0 to 1.0
  - reason: one sentence
  - caveat: one sentence or null
Return only valid JSON. No markdown. No explanation."""


class TarpSpaceMatcher:
    def __init__(self, db_session):
        log.info(f"Loading embedding model: {EMBED_MODEL}")
        self.model = SentenceTransformer(EMBED_MODEL)
        self.db = db_session
        self.agents = []
        self.index = None
        self._load_inventory()

    def _load_inventory(self):
        from db.database import seed_inventory
        seed_inventory(self.db)

        rows = self.db.execute(text(
            "SELECT id, name, category, mandate FROM inventory WHERE is_active = true"
        )).fetchall()

        self.agents = [
            {"id": str(r[0]), "name": r[1], "category": r[2], "mandate": r[3]}
            for r in rows
        ]

        if not self.agents:
            log.warning("No agents found in inventory")
            return

        mandates = [a["mandate"] for a in self.agents]
        log.info(f"Embedding {len(mandates)} inventory items")
        embeddings = self.model.encode(mandates, normalize_embeddings=True)
        self.index = np.array(embeddings, dtype="float32")
        log.info("Inventory index ready")

    def _vector_search(self, query, top_k):
        q_emb = self.model.encode([query], normalize_embeddings=True)
        q_vec = np.array(q_emb[0], dtype="float32")
        scores = self.index @ q_vec
        top_indices = np.argsort(scores)[::-1][:top_k]
        return [(self.agents[i], float(scores[i])) for i in top_indices]

    def _validate_with_llm(self, query, candidates):
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            log.warning("No API key — skipping LLM validation")
            return None

        candidate_text = "\n".join([
            f"ID: {c['id']} | Name: {c['name']} | Category: {c['category']} | Mandate: {c['mandate']}"
            for c in candidates
        ])

        user_msg = f"User query: {query}\n\nCandidates:\n{candidate_text}"

        try:
            resp = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": LLM_MODEL,
                    "messages": [
                        {"role": "system", "content": VALIDATION_SYSTEM},
                        {"role": "user", "content": user_msg}
                    ]
                },
                timeout=30
            )
            raw = resp.json()["choices"][0]["message"]["content"].strip()
            return json.loads(raw)
        except Exception as e:
            log.error(f"LLM validation failed: {e}")
            return None

    def _save_search_run(self, query, result_count, latency_ms, mandate_id=None):
        run_id = str(uuid.uuid4())
        self.db.execute(text("""
            INSERT INTO search_runs (id, mandate_id, query, result_count, latency_ms)
            VALUES (:id, :mandate_id, :query, :result_count, :latency_ms)
        """), {
            "id": run_id,
            "mandate_id": mandate_id,
            "query": query,
            "result_count": result_count,
            "latency_ms": latency_ms
        })
        self.db.commit()
        return run_id

    def _save_search_results(self, search_run_id, results):
        for r in results:
            self.db.execute(text("""
                INSERT INTO search_results (
                    id, search_run_id, inventory_id,
                    similarity_score, alignment_score,
                    match, explanation, caveat
                ) VALUES (
                    gen_random_uuid(), :run_id, :inventory_id,
                    :similarity_score, :alignment_score,
                    :match, :explanation, :caveat
                )
            """), {
                "run_id": search_run_id,
                "inventory_id": r.get("id"),
                "similarity_score": r.get("similarity"),
                "alignment_score": r.get("score"),
                "match": r.get("match", False),
                "explanation": r.get("reason"),
                "caveat": r.get("caveat")
            })
        self.db.commit()

    def match(self, query, top_k=TOP_K, mandate_id=None, mandate=None, owner_id=None):
        t0 = time.time()
        candidates_with_scores = self._vector_search(query, top_k)
        candidates = [a for a, _ in candidates_with_scores]
        similarities = {a["id"]: s for a, s in candidates_with_scores}

        validated = self._validate_with_llm(query, candidates)

        results = []
        if validated:
            for item in validated:
                item["similarity"] = similarities.get(item["id"], 0.0)
                results.append(item)
            results.sort(key=lambda x: x.get("score", 0), reverse=True)
        else:
            for agent, sim in candidates_with_scores:
                results.append({
                    "id": agent["id"],
                    "name": agent["name"],
                    "category": agent["category"],
                    "mandate": agent["mandate"],
                    "similarity": sim,
                    "match": None,
                    "score": None,
                    "reason": None,
                    "caveat": None
                })

        latency_ms = int((time.time() - t0) * 1000)
        run_id = self._save_search_run(query, len(results), latency_ms, mandate_id)
        self._save_search_results(run_id, results)

        return {
            "query": query,
            "search_run_id": run_id,
            "latency_ms": latency_ms,
            "results": results
        }
