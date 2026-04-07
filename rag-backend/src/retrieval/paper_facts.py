"""Lightweight structured fact extraction from chunk text.

Extracts dataset names, metric expressions, model/architecture names,
and method keywords using regex + keyword heuristics.  No LLM call —
fully deterministic and fast.

Usage::

    from src.retrieval.paper_facts import extract_paper_facts
    enriched_chunks = extract_paper_facts(chunks)
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Dict, List, Set


# ── Known architecture stems ─────────────────────────────────────

_KNOWN_MODELS: Set[str] = {
    "u-net", "unet", "resnet", "vgg", "alexnet", "googlenet", "inception",
    "densenet", "efficientnet", "mobilenet", "squeezenet", "shufflenet",
    "yolo", "yolov3", "yolov4", "yolov5", "yolov7", "yolov8",
    "faster r-cnn", "faster rcnn", "mask r-cnn", "mask rcnn", "r-cnn", "rcnn",
    "ssd", "retinanet", "detr", "vit", "swin", "deit",
    "bert", "scibert", "roberta", "gpt", "transformer",
    "lstm", "gru", "rnn", "cnn", "fcn", "gan", "vae",
    "autoencoder", "random forest", "svm", "k-means", "kmeans",
    "xgboost", "lightgbm", "decision tree", "naive bayes",
    "logistic regression", "linear regression", "knn",
    "segnet", "deeplab", "deeplabv3", "pspnet", "fpn",
    "attention", "self-attention", "multi-head attention",
}

# Lowercase set for fast lookup
_KNOWN_MODELS_LOWER = {m.lower() for m in _KNOWN_MODELS}

# ── Dataset trigger phrases ──────────────────────────────────────

_DATASET_TRIGGERS = [
    "on the", "using the", "evaluated on", "trained on",
    "benchmark on", "tested on", "from the", "dataset:",
]

_DATASET_SUFFIX_PATTERNS = re.compile(
    r"\b[A-Z][A-Za-z0-9]*[-]?(?:DB|IDB|Set|Net|Dataset|Benchmark|Corpus)\b"
)

# ── Metric patterns ──────────────────────────────────────────────

_METRIC_PERCENT = re.compile(
    r"(\d{1,3}(?:\.\d{1,2})?)\s*%"
)

_METRIC_EQUALS = re.compile(
    r"(accuracy|precision|recall|f1|f1-score|f-score|auc|auroc|auc-roc|iou|dice|mAP|map|specificity|sensitivity)"
    r"\s*[=:]\s*(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)

_METRIC_NATURAL = re.compile(
    r"(accuracy|precision|recall|f1|auc|iou|dice|mAP|specificity|sensitivity)"
    r"\s+(?:of|is|was|reached|achieved)\s+(\d+(?:\.\d+)?)\s*%?",
    re.IGNORECASE,
)

# ── Method-action verbs ──────────────────────────────────────────

_METHOD_VERBS = {
    "segment", "segmenting", "segmented", "segmentation",
    "classify", "classifying", "classified", "classification",
    "detect", "detecting", "detected", "detection",
    "threshold", "thresholding",
    "cluster", "clustering", "clustered",
    "convolve", "convolving", "convolution",
    "train", "training", "trained",
    "evaluate", "evaluating", "evaluated", "evaluation",
    "extract", "extracting", "extracted", "extraction",
    "preprocess", "preprocessing",
    "augment", "augmenting", "augmentation",
    "normalize", "normalizing", "normalization",
    "denoise", "denoising",
    "filter", "filtering",
    "transform", "transforming",
    "encode", "encoding",
    "decode", "decoding",
    "predict", "predicting", "prediction",
}


def _extract_datasets(text: str) -> List[str]:
    """Extract named datasets from chunk text."""
    datasets: Set[str] = set()

    # Strategy 1: ALLCAPS tokens 3-10 chars (e.g. LISC, BCCD, ALL-IDB)
    for match in re.finditer(r"\b([A-Z][A-Z0-9\-]{2,9})\b", text):
        token = match.group(1)
        # Filter out common abbreviations that aren't datasets
        if token in {"AND", "THE", "FOR", "NOT", "BUT", "CNN", "RNN", "GAN",
                      "SVM", "GPU", "CPU", "RGB", "HSV", "ROI", "PDF", "URL",
                      "API", "SQL", "XML", "JSON", "HTML", "HTTP", "FTP",
                      "IEEE", "ACM", "CVPR", "ICCV", "ECCV", "NIPS", "ICML",
                      "AAAI", "IJCAI", "DOI", "ISSN", "ISBN"}:
            continue
        datasets.add(token)

    # Strategy 2: Known suffix patterns (-DB, -IDB, Dataset, etc.)
    for match in _DATASET_SUFFIX_PATTERNS.finditer(text):
        datasets.add(match.group(0))

    # Strategy 3: Tokens following trigger phrases
    text_lower = text.lower()
    for trigger in _DATASET_TRIGGERS:
        idx = 0
        while True:
            pos = text_lower.find(trigger, idx)
            if pos < 0:
                break
            after = text[pos + len(trigger):].strip()
            # Capture the next 1-4 words as a potential dataset name
            words = after.split()[:4]
            candidate = " ".join(words).strip(" .,;:()")
            if candidate and len(candidate) > 2:
                # Clean trailing punctuation
                candidate = re.sub(r"[.,;:()]+$", "", candidate).strip()
                if candidate:
                    datasets.add(candidate)
            idx = pos + len(trigger)

    return sorted(datasets)


def _extract_metrics(text: str) -> List[str]:
    """Extract metric expressions from chunk text."""
    metrics: List[str] = []

    # Pattern 1: NN.N% (e.g. "98.4%", "97.3 %")
    for match in _METRIC_PERCENT.finditer(text):
        value = match.group(1)
        # Try to find what metric this belongs to by looking back
        prefix = text[:match.start()].split()[-3:] if match.start() > 0 else []
        prefix_str = " ".join(prefix).lower()
        metric_name = ""
        for name in ["accuracy", "precision", "recall", "f1", "auc", "iou", "dice",
                      "specificity", "sensitivity", "mAP"]:
            if name in prefix_str:
                metric_name = name
                break
        if metric_name:
            metrics.append(f"{metric_name} {value}%")
        else:
            metrics.append(f"{value}%")

    # Pattern 2: metric=N.NN or metric: N.NN
    for match in _METRIC_EQUALS.finditer(text):
        metrics.append(f"{match.group(1)}={match.group(2)}")

    # Pattern 3: "accuracy of 98.4%"
    for match in _METRIC_NATURAL.finditer(text):
        val = match.group(2)
        metrics.append(f"{match.group(1)} {val}%")

    # Deduplicate while preserving order
    seen: Set[str] = set()
    unique: List[str] = []
    for m in metrics:
        key = m.lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(m)
    return unique


def _extract_model_names(text: str) -> List[str]:
    """Extract model/architecture names from chunk text."""
    models: Set[str] = set()
    text_lower = text.lower()

    # Strategy 1: Match known architecture stems
    for model in _KNOWN_MODELS_LOWER:
        # Use word boundary for short names, substring for longer
        if len(model) <= 3:
            pattern = r"\b" + re.escape(model) + r"\b"
        else:
            pattern = re.escape(model)
        if re.search(pattern, text_lower):
            models.add(model)

    # Strategy 2: Versioned model names (e.g. ResNet-50, VGG-16, EfficientNet-B0)
    for match in re.finditer(
        r"\b(ResNet|VGG|Inception|DenseNet|EfficientNet|MobileNet|YOLOv?\d?)"
        r"[-\s]?(\d+|[BbSsLlMm]\d?)\b",
        text,
    ):
        models.add(match.group(0).lower())

    # Strategy 3: CamelCase tokens near "proposed" (e.g. "proposed DeepBloodNet")
    for match in re.finditer(
        r"(?:proposed|introduce[ds]?|present[eds]?|our)\s+([A-Z][a-z]+(?:[A-Z][a-z]+)+)",
        text,
    ):
        models.add(match.group(1).lower())

    return sorted(models)


def _extract_method_keywords(text: str) -> List[str]:
    """Extract method action phrases (2-3 gram window around action verbs)."""
    words = text.lower().split()
    method_phrases: List[str] = []

    for i, word in enumerate(words):
        clean_word = re.sub(r"[^a-z]", "", word)
        if clean_word in _METHOD_VERBS:
            # Build 2-3 gram window around the verb
            start = max(0, i - 1)
            end = min(len(words), i + 2)
            phrase = " ".join(words[start:end])
            # Clean punctuation
            phrase = re.sub(r"[.,;:()\"'\[\]{}]", "", phrase).strip()
            if phrase and len(phrase) > 4:
                method_phrases.append(phrase)

    # Return top 5 by frequency
    counts = Counter(method_phrases)
    return [phrase for phrase, _ in counts.most_common(5)]


def extract_paper_facts(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract structured comparison facts from each chunk's text.

    Adds a ``paper_facts`` dict to each chunk with keys:
      - datasets: List[str]   — named datasets found
      - metrics: List[str]    — metric expressions found
      - model_names: List[str] — architecture names found
      - method_keywords: List[str] — method action phrases

    This is fully deterministic (regex + keyword heuristics, no LLM).

    Args:
        chunks: List of chunk dicts, each must have at least ``text``.

    Returns:
        The same list with ``paper_facts`` added to each chunk.
    """
    for chunk in chunks:
        text = chunk.get("text", "")
        if not text:
            chunk["paper_facts"] = {
                "datasets": [],
                "metrics": [],
                "model_names": [],
                "method_keywords": [],
            }
            continue

        chunk["paper_facts"] = {
            "datasets": _extract_datasets(text),
            "metrics": _extract_metrics(text),
            "model_names": _extract_model_names(text),
            "method_keywords": _extract_method_keywords(text),
        }

    return chunks
