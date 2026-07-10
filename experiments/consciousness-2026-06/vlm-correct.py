#!/usr/bin/env python3
from transformers import CLIPModel, CLIPProcessor

class VLM:
    def __init__(self):
        self.model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
        self.processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
    
    def embed_text(self, text):
        inputs = self.processor(text=[text], return_tensors="pt")
        outputs = self.model.get_text_features(**inputs)
        # FIX: outputs is BaseModelOutputWithPooling - need to access the actual tensor
        # Check what attributes it has
        return outputs[0].numpy() if hasattr(outputs, '__getitem__') else str(type(outputs))

if __name__ == '__main__':
    vlm = VLM()
    result = vlm.embed_text("test")
    print(f"Result: {result if isinstance(result, str) else result.shape}")
