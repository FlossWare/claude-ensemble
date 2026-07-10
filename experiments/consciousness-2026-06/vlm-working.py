#!/usr/bin/env python3
"""VLM - Working version"""
from transformers import CLIPProcessor, CLIPModel
import torch

class VLMIntegration:
    def __init__(self):
        self.model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
        self.processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
    
    def process_text(self, text):
        inputs = self.processor(text=[text], return_tensors="pt", padding=True)
        with torch.no_grad():
            outputs = self.model.get_text_features(**inputs)
        # FIX: Use .detach().numpy() not .numpy()
        return {
            'text_embedding': outputs.detach().numpy(),
            'shape': tuple(outputs.shape)
        }

if __name__ == '__main__':
    vlm = VLMIntegration()
    result = vlm.process_text("test")
    print(f"✅ VLM working")
    print(f"   Embedding shape: {result['shape']}")
