"""
TTB Label Review — local LLM model loader
Wraps the locally available SmolVLM transformer models.
"""

import os
from pathlib import Path

import config as cfg

_model_cfg = cfg.get("model", {})
MODELS_DIR = Path(__file__).parent / _model_cfg.get("models_dir", "models")
DEFAULT_MODEL = _model_cfg.get("name", "SmolVLM-500M-Instruct")


class LabelReviewModel:

    def __init__(self, model_name: str = DEFAULT_MODEL):
        self.model_name = model_name
        self.model_path = MODELS_DIR / model_name
        self.processor = None
        self.model = None

    def load(self):
        """Load processor and model from local path."""
        from transformers import AutoProcessor, AutoModelForVision2Seq
        import torch

        print(f"Loading model from {self.model_path} ...")
        self.processor = AutoProcessor.from_pretrained(str(self.model_path), local_files_only=True)
        self.model = AutoModelForVision2Seq.from_pretrained(
            str(self.model_path),
            local_files_only=True,
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        )
        self.model.eval()
        print("Model loaded.")

    def review(self, image_path: str, prompt: str = None) -> dict:
        """
        Run inference on a label image.
        Returns a dict with model output and metadata.
        """
        from PIL import Image

        if self.model is None:
            raise RuntimeError("Model not loaded — call load() first.")

        if prompt is None:
            prompt = (
                "You are reviewing a TTB COLA wine label submission. "
                "Describe what you see and flag any compliance concerns."
            )

        image = Image.open(image_path).convert("RGB")
        inputs = self.processor(text=prompt, images=image, return_tensors="pt")

        import torch
        with torch.no_grad():
            output = self.model.generate(**inputs, max_new_tokens=256)

        result_text = self.processor.decode(output[0], skip_special_tokens=True)
        return {
            "model": self.model_name,
            "image": image_path,
            "prompt": prompt,
            "result": result_text,
        }


# Module-level singleton — loaded once and reused across requests
_instance: LabelReviewModel = None


def get_model(model_name: str = DEFAULT_MODEL) -> LabelReviewModel:
    global _instance
    if _instance is None:
        _instance = LabelReviewModel(model_name)
        _instance.load()
    return _instance
