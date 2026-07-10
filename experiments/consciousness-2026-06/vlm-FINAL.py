#!/usr/bin/env python3
"""VLM - Final working version after review iterations"""
from transformers import CLIPProcessor, CLIPModel
import torch

class VLM:
    def __init__(self):
        self.model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
        self.processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
    
    def embed_text(self, text):
        inputs = self.processor(text=[text], return_tensors="pt")
        with torch.no_grad():
            embeds = self.model.get_text_features(**inputs)
        # FIX from review: BaseModelOutputWithPooling has no .cpu(), access tensor directly
        return embeds.detach().cpu().numpy()

if __name__ == '__main__':
    vlm = VLM()
    result = vlm.embed_text("test")
    print(f"✅ VLM working: shape {result.shape}")
