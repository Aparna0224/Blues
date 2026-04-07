"""Shared text utility functions to avoid duplication across modules."""


def keyword_overlap(query: str, text: str, stop_words: set = None) -> int:
    """Count non-stop keyword overlap between query and text."""
    if not query or not text:
        return 0
    _stop = stop_words or {
        "what", "how", "why", "when", "where", "which", "is", "are",
        "does", "do", "can", "the", "a", "an", "in", "of", "and",
        "or", "to", "for", "on", "with", "by", "from", "as", "at",
        "about", "into", "be", "this", "that",
    }
    query_terms = {
        w.strip(".,;:()[]{}\"'`).").lower()
        for w in query.split()
        if w and w.lower() not in _stop and len(w.strip(".,;:()[]{}\"'`).")) > 2
    }
    if not query_terms:
        return 0
    text_terms = {
        w.strip(".,;:()[]{}\"'`).").lower()
        for w in text.split()
        if w and w.lower() not in _stop and len(w.strip(".,;:()[]{}\"'`).")) > 2
    }
    return len(query_terms.intersection(text_terms))
