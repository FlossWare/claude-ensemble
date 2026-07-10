#!/usr/bin/env python3
"""VLM Patterns with transformers"""
try:
    from transformers import CLIPProcessor, CLIPModel
    from PIL import Image
    import numpy as np
    
    class VLMIntegration:
        def __init__(self):
            # Use CLIP for vision-language
            self.model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
            self.processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
        
        def process_multimodal(self, text, image_path=None):
            """Process text and optional image"""
            if image_path:
                image = Image.open(image_path)
                inputs = self.processor(text=[text], images=image, return_tensors="pt", padding=True)
            else:
                inputs = self.processor(text=[text], return_tensors="pt", padding=True)
            
            outputs = self.model(**inputs)
            
            return {
                'text_embedding': outputs.text_embeds.detach().numpy() if hasattr(outputs, 'text_embeds') else None,
                'image_embedding': outputs.image_embeds.detach().numpy() if hasattr(outputs, 'image_embeds') else None,
                'similarity': outputs.logits_per_text.detach().numpy() if hasattr(outputs, 'logits_per_text') else None
            }
    
    if __name__ == '__main__':
        vlm = VLMIntegration()
        result = vlm.process_multimodal("a photo of a cat")
        print("VLM with transformers: ✓ WORKING")
        print(f"  CLIP loaded: ✓")
        print(f"  Text embedding shape: {result['text_embedding'].shape if result['text_embedding'] is not None else 'N/A'}")

except ImportError as e:
    print(f"❌ transformers not available: {e}")
    print("Install: pip3 install --user transformers pillow")
