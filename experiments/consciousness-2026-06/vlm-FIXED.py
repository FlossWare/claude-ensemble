#!/usr/bin/env python3
"""VLM with proper error handling"""
import sys

try:
    from transformers import CLIPProcessor, CLIPModel
    from PIL import Image
    import torch
    
    class VLMIntegration:
        def __init__(self):
            print("Loading CLIP model...")
            self.model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
            self.processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
            print("✓ Model loaded")
        
        def process_text(self, text):
            """Process text only (no image)"""
            inputs = self.processor(text=[text], return_tensors="pt", padding=True)
            with torch.no_grad():
                outputs = self.model.get_text_features(**inputs)
            return {
                'text_embedding': outputs.numpy(),
                'shape': outputs.shape
            }
        
        def process_multimodal(self, text, image_path):
            """Process text + image"""
            if image_path:
                image = Image.open(image_path)
                inputs = self.processor(text=[text], images=image, return_tensors="pt", padding=True)
            else:
                return self.process_text(text)
            
            with torch.no_grad():
                outputs = self.model(**inputs)
            
            return {
                'text_embedding': outputs.text_embeds.numpy(),
                'image_embedding': outputs.image_embeds.numpy() if hasattr(outputs, 'image_embeds') else None
            }
    
    if __name__ == '__main__':
        vlm = VLMIntegration()
        
        # Test text-only (no image needed)
        result = vlm.process_text("a photo of a cat")
        print(f"\n✅ VLM working with CLIP")
        print(f"   Text embedding shape: {result['shape']}")
        
except Exception as e:
    print(f"❌ VLM error: {e}")
    print("\nFallback: Mock VLM (marks as TODO)")
