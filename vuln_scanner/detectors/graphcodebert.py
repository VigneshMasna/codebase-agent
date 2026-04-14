from __future__ import annotations

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from vuln_scanner.config.settings import get_settings


class GraphCodeBERTDetector:
    def __init__(self) -> None:
        settings = get_settings()

        print("Loading GraphCodeBERT models...")

        c_model_id    = settings.graphcodebert_c_model_id
        java_model_id = settings.graphcodebert_java_model_id

        try:
            self.c_tokenizer = AutoTokenizer.from_pretrained(c_model_id)
            self.c_model = AutoModelForSequenceClassification.from_pretrained(c_model_id)
            self.java_tokenizer = AutoTokenizer.from_pretrained(java_model_id)
            self.java_model = AutoModelForSequenceClassification.from_pretrained(java_model_id)
        except OSError as exc:
            raise RuntimeError(
                f"Failed to load GraphCodeBERT models: {exc}. "
                "Check GRAPHCODEBERT_C_MODEL_ID and GRAPHCODEBERT_JAVA_MODEL_ID in .env."
            ) from exc
        except Exception as exc:
            raise RuntimeError(f"Unexpected error loading GraphCodeBERT models: {exc}") from exc

        self.c_model.eval()
        self.java_model.eval()

        print("Models loaded")

    def detect_bug(self, code: str, language: str) -> tuple[str, float]:
        code = code.strip()
        if not code:
            return "SAFE", 0.0

        if language in ["c", "cpp"]:
            tokenizer = self.c_tokenizer
            model = self.c_model
        elif language == "java":
            tokenizer = self.java_tokenizer
            model = self.java_model
        else:
            raise ValueError("Unsupported language")

        inputs = tokenizer(
            code,
            return_tensors="pt",
            truncation=True,
            padding=True,
            max_length=512,
        )

        with torch.no_grad():
            outputs = model(**inputs)

        logits = outputs.logits

        # Temperature=1.5: mild calibration that preserves signal without
        # over-flattening confident predictions (3.0 was too aggressive).
        temperature = 1.5
        probs = torch.softmax(logits / temperature, dim=1)

        safe_prob = probs[0][0].item()
        bug_prob  = probs[0][1].item()

        # Use a slight positive bias (0.52) to reduce false positives
        # while keeping high-confidence detections.
        if bug_prob >= 0.52:
            label      = "BUG"
            confidence = bug_prob
        else:
            label      = "SAFE"
            confidence = safe_prob

        return label, confidence
