"""RAG-01: Evaluation harness for retrieval and answers.

Metrics: Recall@1/3/5, MRR, citation validity, abstention accuracy.
Usage: python benchmarks/rag_eval.py [--quick]
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from studybuddy.pdf_qa import (  # noqa: E402
    answer_question,
    chunk_pages,
    retrieve,
    verify_citations,
)

GOLD_DIR = os.path.join(os.path.dirname(__file__), "rag_gold")


def recall_at_k(ranked_ids, gold_ids, k):
    topk = set(ranked_ids[:k])
    hits = len(topk & set(gold_ids))
    return hits / len(gold_ids) if gold_ids else 1.0


def mrr(ranked_ids, gold_ids):
    gold = set(gold_ids)
    for i, rid in enumerate(ranked_ids):
        if rid in gold:
            return 1.0 / (i + 1)
    return 0.0


def evaluate(quick=False):
    # Build a synthetic corpus: 3 fake "papers" with known content
    docs = {
        "paper_a": (
            "Machine learning models require large datasets for training. "
            "The transformer architecture revolutionized natural language processing in 2017. "
            "Attention mechanisms allow models to focus on relevant input parts. "
            "BERT and GPT are prominent transformer-based models. "
        ) * 3,
        "paper_b": (
            "Climate change accelerates polar ice melt. "
            "Rising sea levels threaten coastal cities worldwide. "
            "Carbon capture technology shows promise for emission reduction. "
            "Renewable energy adoption grew 12 percent last year. "
        ) * 3,
        "paper_c": (
            "Quantum computing uses qubits for parallel computation. "
            "Shor's algorithm factors large numbers efficiently. "
            "Quantum supremacy was claimed by Google in 2019. "
            "Error correction remains a major challenge. "
        ) * 3,
    }
    # Chunk each doc
    chunked = {}
    for doc_id, text in docs.items():
        chunks = chunk_pages([text], chunk_chars=400, overlap=50)
        # tag chunks with doc id
        for i, c in enumerate(chunks):
            c["chunk_id"] = f"{doc_id}#{i}"
        chunked[doc_id] = chunks

    all_chunks = [c for cl in chunked.values() for c in cl]

    # Gold Q&A: (question, gold_doc, answerable)
    qa = [
        ("What architecture revolutionized NLP in 2017?", "paper_a", True),
        ("Which models are transformer-based?", "paper_a", True),
        ("What threatens coastal cities?", "paper_b", True),
        ("How much did renewable adoption grow?", "paper_b", True),
        ("What does Shor's algorithm do?", "paper_c", True),
        ("When was quantum supremacy claimed?", "paper_c", True),
        # Unanswerable (not in corpus)
        ("What is the capital of Mars?", None, False),
        ("How do dolphins communicate?", None, False),
    ]
    if quick:
        qa = qa[:4]

    recalls = {1: [], 3: [], 5: []}
    mrrs = []
    abstain_ok = 0
    abstain_total = 0
    cite_ok = 0
    cite_total = 0

    for question, gold_doc, answerable in qa:
        ranked = retrieve(all_chunks, question, top_k=5)
        ranked_ids = [c["chunk_id"].split("#")[0] for c in ranked]

        if answerable:
            gold_ids = [gold_doc]
            for k in recalls:
                recalls[k].append(recall_at_k(ranked_ids, gold_ids, k))
            mrrs.append(mrr(ranked_ids, gold_ids))
        else:
            abstain_total += 1

        # Answer + citation check
        ans = answer_question(question, "eval", all_chunks, top_k=3)
        if not answerable:
            # Should abstain
            if "couldn't find" in ans["answer"]:
                abstain_ok += 1
        else:
            cite_total += 1
            v = verify_citations(ans)
            if v["ok"]:
                cite_ok += 1

    results = {
        "n_questions": len(qa),
        "recall@1": sum(recalls[1]) / len(recalls[1]) if recalls[1] else 0,
        "recall@3": sum(recalls[3]) / len(recalls[3]) if recalls[3] else 0,
        "recall@5": sum(recalls[5]) / len(recalls[5]) if recalls[5] else 0,
        "mrr": sum(mrrs) / len(mrrs) if mrrs else 0,
        "abstention_accuracy": abstain_ok / abstain_total if abstain_total else 0,
        "citation_validity": cite_ok / cite_total if cite_total else 0,
    }
    return results


def main():
    quick = "--quick" in sys.argv
    results = evaluate(quick=quick)
    print(json.dumps(results, indent=2))
    out = os.path.join(os.path.dirname(__file__), "rag_results.json")
    with open(out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
