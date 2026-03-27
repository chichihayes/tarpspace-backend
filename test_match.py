import os
import sys
import json
from dotenv import load_dotenv

load_dotenv()

from db.database import SessionLocal
from core.matcher import TarpSpaceMatcher

DEMO_QUERIES = [
    "I need a React developer for a fintech project",
    "Looking for a mid-century modern couch under $500",
    "Need a machine learning study partner",
    "Selling a vintage leather sofa in good condition",
    "Looking for a plumber in Houston this weekend",
]


def run_query(query, matcher):
    print(f"\n{'='*70}")
    print(f"QUERY: {query}")
    result = matcher.match(query)
    print(f"Latency: {result['latency_ms']}ms")
    print(f"Search Run ID: {result['search_run_id']}")
    print(f"{'-'*70}")

    has_validation = any(r.get("match") is not None for r in result["results"])

    if has_validation:
        matched = [r for r in result["results"] if r.get("match")]
        not_matched = [r for r in result["results"] if not r.get("match")]

        print(f"MATCHES ({len(matched)}):")
        for r in matched:
            print(f"  [{r['id'][:8]}] score: {r.get('score', 0):.2f} | {r.get('reason', '')}")
            if r.get("caveat"):
                print(f"    caveat: {r['caveat']}")

        if not_matched:
            print(f"\nNOT A MATCH ({len(not_matched)}):")
            for r in not_matched:
                print(f"  [{r['id'][:8]}] {r.get('reason', '')}")
    else:
        print("VECTOR-ONLY (no LLM validation — check OPENROUTER_API_KEY):")
        for r in result["results"]:
            print(f"  [{r['id'][:8]}] {r.get('name', '')} | similarity: {r['similarity']:.3f}")

    print(f"{'='*70}")


def main():
    db = SessionLocal()
    try:
        print("Loading matcher (first run downloads the model ~1.3GB)...")
        matcher = TarpSpaceMatcher(db)

        if "--demo" in sys.argv:
            for q in DEMO_QUERIES:
                run_query(q, matcher)
        elif len(sys.argv) > 1:
            query = " ".join(a for a in sys.argv[1:] if not a.startswith("--"))
            if query:
                run_query(query, matcher)
            else:
                print("Usage: python test_match.py \"your query here\"")
                print("       python test_match.py --demo")
        else:
            print("Usage: python test_match.py \"your query here\"")
            print("       python test_match.py --demo")
    finally:
        db.close()


if __name__ == "__main__":
    main()
