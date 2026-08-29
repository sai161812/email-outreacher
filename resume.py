"""
You keep one base resume plus a handful of interchangeable variants
(e.g. backend-focused, ML-focused). This module registers them and
picks the best match for a given job text — it does NOT generate or
rewrite resume content. That stays under your control, on purpose:
letting an LLM freely rewrite claims about your own work is a bad idea.
"""
from db import get_connection


def add_resume_variant(name, keywords, file_path, resume_url=None):
    """
    keywords: comma-separated string, e.g. "backend,api,django,sql"
    file_path: path to the actual resume file (PDF) for this variant
    resume_url: optional public link to view resume online
    """
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO resume_variants (name, keywords, file_path, resume_url) VALUES (?, ?, ?, ?)",
            (name, keywords, file_path, resume_url),
        )
        return cur.lastrowid


def get_variant(variant_id: int):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM resume_variants WHERE id = ?", (variant_id,)).fetchone()
        return dict(row) if row else None


def list_resume_variants():
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM resume_variants").fetchall()
        return [dict(r) for r in rows]


def pick_best_variant(job_text: str):
    """
    Naive keyword-overlap scoring. Good enough for a handful of variants;
    replace with something smarter only if you actually end up with many.
    """
    variants = list_resume_variants()
    if not variants:
        return None
    if not job_text:
        return variants[0]  # fall back to first registered variant

    job_text_lower = job_text.lower()
    best, best_score = None, -1
    for v in variants:
        keywords = [k.strip().lower() for k in v["keywords"].split(",") if k.strip()]
        score = sum(1 for k in keywords if k in job_text_lower)
        if score > best_score:
            best, best_score = v, score
    return best
