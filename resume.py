from repository import ResumeRepository

def add_resume_variant(name, keywords, file_path, resume_url=None):
    return ResumeRepository.create(name, keywords, file_path, resume_url)

def list_resume_variants():
    return [dict(r) for r in ResumeRepository.get_all()]

def pick_best_variant(job_text: str):
    job_text = job_text.lower()
    variants = list_resume_variants()
    if not variants:
        return None

    best_match = None
    best_score = -1

    for v in variants:
        keywords = [k.strip().lower() for k in v["keywords"].split(",") if k.strip()]
        score = sum(1 for k in keywords if k in job_text)
        if score > best_score:
            best_score = score
            best_match = v

    if best_score > 0:
        return best_match
    return variants[0]
