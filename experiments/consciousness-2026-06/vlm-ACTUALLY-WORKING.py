#!/usr/bin/env python3
from transformers import CLIPProcessor, CLIPModel

class VLM:
    def __init__(self):
        self.model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
        self.processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
    
    def embed_text(self, text):
        inputs = self.processor(text=[text], return_tensors="pt")
        outputs = self.model.get_text_features(**inputs)
        # FIX: It's already a tensor, just convert directly
        return outputs.numpy()

if __name__ == '__main__':
    vlm = VLM()
    result = vlm.embed_text("test")
    print(f"✅ VLM working: shape {result.shape}")
