#!/usr/bin/env python3
"""Hugging Face documentation scraper.

Covers:
  - Transformers (models, training, pipelines, tokenizers, tasks)
  - Datasets (loading, processing, metrics)
  - Diffusers (stable diffusion, training, pipelines)
  - Hub (repositories, models, datasets, spaces)
  - PEFT (LoRA, adapters, prompt tuning)
  - Accelerate (distributed training, DeepSpeed, FSDP)
  - Tokenizers (pipeline, components, API)
  - Evaluate (metrics, evaluators)
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class HuggingFaceScraper(BaseScraper):
    """Scrape Hugging Face documentation across all major libraries."""

    SOURCES = {
        "transformers-quicktour": {
            "pages": {
                "https://huggingface.co/docs/transformers/index": "Transformers Documentation",
                "https://huggingface.co/docs/transformers/quicktour": "Quick Tour",
                "https://huggingface.co/docs/transformers/installation": "Installation",
                "https://huggingface.co/docs/transformers/philosophy": "Philosophy",
                "https://huggingface.co/docs/transformers/glossary": "Glossary",
                "https://huggingface.co/docs/transformers/task_summary": "Task Summary",
            },
        },
        "transformers-pipeline": {
            "pages": {
                "https://huggingface.co/docs/transformers/pipeline_tutorial": "Pipelines for Inference",
                "https://huggingface.co/docs/transformers/main_classes/pipelines": "Pipelines API",
                "https://huggingface.co/docs/transformers/pipeline_webserver": "Pipeline Web Server",
                "https://huggingface.co/docs/transformers/conversations": "Conversational Pipeline",
            },
        },
        "transformers-autoclass": {
            "pages": {
                "https://huggingface.co/docs/transformers/autoclass_tutorial": "AutoClass Tutorial",
                "https://huggingface.co/docs/transformers/model_doc/auto": "Auto Classes",
                "https://huggingface.co/docs/transformers/main_classes/model": "PreTrainedModel",
                "https://huggingface.co/docs/transformers/main_classes/configuration": "Configuration",
            },
        },
        "transformers-training": {
            "pages": {
                "https://huggingface.co/docs/transformers/training": "Training and Fine-tuning",
                "https://huggingface.co/docs/transformers/main_classes/trainer": "Trainer",
                "https://huggingface.co/docs/transformers/main_classes/deepspeed": "DeepSpeed Integration",
                "https://huggingface.co/docs/transformers/perf_train_gpu_one": "Efficient Training on a Single GPU",
                "https://huggingface.co/docs/transformers/perf_train_gpu_many": "Efficient Training on Multiple GPUs",
                "https://huggingface.co/docs/transformers/perf_train_cpu": "Efficient Training on CPU",
                "https://huggingface.co/docs/transformers/perf_train_tpu": "Efficient Training on TPU",
                "https://huggingface.co/docs/transformers/perf_train_special": "Specialized Hardware Training",
                "https://huggingface.co/docs/transformers/perf_hardware": "Custom Hardware for Training",
                "https://huggingface.co/docs/transformers/hpo_train": "Hyperparameter Search",
                "https://huggingface.co/docs/transformers/trainer_distributed": "Distributed Training",
                "https://huggingface.co/docs/transformers/main_classes/callback": "Callbacks",
                "https://huggingface.co/docs/transformers/main_classes/optimizer_schedules": "Optimizers and Schedulers",
                "https://huggingface.co/docs/transformers/main_classes/logging": "Logging",
            },
        },
        "transformers-tokenizer": {
            "pages": {
                "https://huggingface.co/docs/transformers/tokenizer_summary": "Tokenizer Summary",
                "https://huggingface.co/docs/transformers/main_classes/tokenizer": "Tokenizer",
                "https://huggingface.co/docs/transformers/fast_tokenizers": "Fast Tokenizers",
                "https://huggingface.co/docs/transformers/multilingual": "Multilingual Models",
            },
        },
        "transformers-model": {
            "pages": {
                "https://huggingface.co/docs/transformers/model_doc/bert": "BERT",
                "https://huggingface.co/docs/transformers/model_doc/gpt2": "GPT-2",
                "https://huggingface.co/docs/transformers/model_doc/gpt_neo": "GPT-Neo",
                "https://huggingface.co/docs/transformers/model_doc/gpt_neox": "GPT-NeoX",
                "https://huggingface.co/docs/transformers/model_doc/gptj": "GPT-J",
                "https://huggingface.co/docs/transformers/model_doc/llama": "LLaMA",
                "https://huggingface.co/docs/transformers/model_doc/llama2": "Llama 2",
                "https://huggingface.co/docs/transformers/model_doc/llama3": "Llama 3",
                "https://huggingface.co/docs/transformers/model_doc/mistral": "Mistral",
                "https://huggingface.co/docs/transformers/model_doc/mixtral": "Mixtral",
                "https://huggingface.co/docs/transformers/model_doc/gemma": "Gemma",
                "https://huggingface.co/docs/transformers/model_doc/gemma2": "Gemma 2",
                "https://huggingface.co/docs/transformers/model_doc/phi": "Phi",
                "https://huggingface.co/docs/transformers/model_doc/phi3": "Phi-3",
                "https://huggingface.co/docs/transformers/model_doc/qwen2": "Qwen2",
                "https://huggingface.co/docs/transformers/model_doc/falcon": "Falcon",
                "https://huggingface.co/docs/transformers/model_doc/t5": "T5",
                "https://huggingface.co/docs/transformers/model_doc/mt5": "mT5",
                "https://huggingface.co/docs/transformers/model_doc/bart": "BART",
                "https://huggingface.co/docs/transformers/model_doc/mbart": "mBART",
                "https://huggingface.co/docs/transformers/model_doc/pegasus": "PEGASUS",
                "https://huggingface.co/docs/transformers/model_doc/roberta": "RoBERTa",
                "https://huggingface.co/docs/transformers/model_doc/distilbert": "DistilBERT",
                "https://huggingface.co/docs/transformers/model_doc/albert": "ALBERT",
                "https://huggingface.co/docs/transformers/model_doc/electra": "ELECTRA",
                "https://huggingface.co/docs/transformers/model_doc/deberta": "DeBERTa",
                "https://huggingface.co/docs/transformers/model_doc/deberta-v2": "DeBERTa-v2",
                "https://huggingface.co/docs/transformers/model_doc/xlnet": "XLNet",
                "https://huggingface.co/docs/transformers/model_doc/xlm-roberta": "XLM-RoBERTa",
                "https://huggingface.co/docs/transformers/model_doc/bloom": "BLOOM",
                "https://huggingface.co/docs/transformers/model_doc/opt": "OPT",
                "https://huggingface.co/docs/transformers/model_doc/vit": "ViT",
                "https://huggingface.co/docs/transformers/model_doc/deit": "DeiT",
                "https://huggingface.co/docs/transformers/model_doc/beit": "BEiT",
                "https://huggingface.co/docs/transformers/model_doc/swin": "Swin Transformer",
                "https://huggingface.co/docs/transformers/model_doc/clip": "CLIP",
                "https://huggingface.co/docs/transformers/model_doc/blip": "BLIP",
                "https://huggingface.co/docs/transformers/model_doc/blip-2": "BLIP-2",
                "https://huggingface.co/docs/transformers/model_doc/sam": "SAM",
                "https://huggingface.co/docs/transformers/model_doc/whisper": "Whisper",
                "https://huggingface.co/docs/transformers/model_doc/wav2vec2": "Wav2Vec2",
                "https://huggingface.co/docs/transformers/model_doc/hubert": "HuBERT",
                "https://huggingface.co/docs/transformers/model_doc/detr": "DETR",
                "https://huggingface.co/docs/transformers/model_doc/yolos": "YOLOS",
                "https://huggingface.co/docs/transformers/model_doc/segformer": "SegFormer",
                "https://huggingface.co/docs/transformers/model_doc/codegen": "CodeGen",
                "https://huggingface.co/docs/transformers/model_doc/starcoder2": "StarCoder2",
            },
        },
        "transformers-preprocessing": {
            "pages": {
                "https://huggingface.co/docs/transformers/preprocessing": "Preprocessing",
                "https://huggingface.co/docs/transformers/main_classes/processors": "Processors",
                "https://huggingface.co/docs/transformers/main_classes/feature_extractor": "Feature Extractor",
                "https://huggingface.co/docs/transformers/main_classes/image_processor": "Image Processor",
            },
        },
        "transformers-fine-tuning": {
            "pages": {
                "https://huggingface.co/docs/transformers/tasks/sequence_classification": "Text Classification",
                "https://huggingface.co/docs/transformers/tasks/token_classification": "Token Classification",
                "https://huggingface.co/docs/transformers/tasks/question_answering": "Question Answering",
                "https://huggingface.co/docs/transformers/tasks/language_modeling": "Causal Language Modeling",
                "https://huggingface.co/docs/transformers/tasks/masked_language_modeling": "Masked Language Modeling",
                "https://huggingface.co/docs/transformers/tasks/translation": "Translation",
                "https://huggingface.co/docs/transformers/tasks/summarization": "Summarization",
                "https://huggingface.co/docs/transformers/tasks/multiple_choice": "Multiple Choice",
                "https://huggingface.co/docs/transformers/tasks/image_classification": "Image Classification",
                "https://huggingface.co/docs/transformers/tasks/semantic_segmentation": "Semantic Segmentation",
                "https://huggingface.co/docs/transformers/tasks/object_detection": "Object Detection",
                "https://huggingface.co/docs/transformers/tasks/video_classification": "Video Classification",
                "https://huggingface.co/docs/transformers/tasks/audio_classification": "Audio Classification",
                "https://huggingface.co/docs/transformers/tasks/asr": "Automatic Speech Recognition",
                "https://huggingface.co/docs/transformers/tasks/text-to-speech": "Text-to-Speech",
                "https://huggingface.co/docs/transformers/tasks/image_to_image": "Image-to-Image",
                "https://huggingface.co/docs/transformers/tasks/zero_shot_image_classification": "Zero-Shot Image Classification",
                "https://huggingface.co/docs/transformers/tasks/zero_shot_object_detection": "Zero-Shot Object Detection",
                "https://huggingface.co/docs/transformers/tasks/document_question_answering": "Document Question Answering",
                "https://huggingface.co/docs/transformers/tasks/visual_question_answering": "Visual Question Answering",
            },
        },
        "transformers-tasks": {
            "pages": {
                "https://huggingface.co/docs/transformers/generation_strategies": "Generation Strategies",
                "https://huggingface.co/docs/transformers/main_classes/text_generation": "Text Generation",
                "https://huggingface.co/docs/transformers/llm_tutorial": "LLM Tutorial",
                "https://huggingface.co/docs/transformers/chat_templating": "Chat Templates",
                "https://huggingface.co/docs/transformers/perplexity": "Perplexity",
                "https://huggingface.co/docs/transformers/serialization": "Serialization",
                "https://huggingface.co/docs/transformers/model_sharing": "Share a Model",
                "https://huggingface.co/docs/transformers/transformers_agents": "Transformers Agents",
                "https://huggingface.co/docs/transformers/add_new_model": "How to Add a Model",
                "https://huggingface.co/docs/transformers/custom_models": "Custom Models",
                "https://huggingface.co/docs/transformers/create_a_model": "Create a Custom Architecture",
                "https://huggingface.co/docs/transformers/quantization": "Quantization",
                "https://huggingface.co/docs/transformers/perf_infer_gpu_one": "GPU Inference",
                "https://huggingface.co/docs/transformers/perf_infer_cpu": "CPU Inference",
                "https://huggingface.co/docs/transformers/big_models": "Instantiate Big Models",
                "https://huggingface.co/docs/transformers/debugging": "Debugging",
                "https://huggingface.co/docs/transformers/community": "Community Resources",
                "https://huggingface.co/docs/transformers/troubleshooting": "Troubleshooting",
                "https://huggingface.co/docs/transformers/migration": "Migration Guide",
            },
        },
        "datasets-loading": {
            "pages": {
                "https://huggingface.co/docs/datasets/index": "Datasets Documentation",
                "https://huggingface.co/docs/datasets/quickstart": "Quickstart",
                "https://huggingface.co/docs/datasets/installation": "Installation",
                "https://huggingface.co/docs/datasets/loading": "Load a Dataset",
                "https://huggingface.co/docs/datasets/load_hub": "Load from Hub",
                "https://huggingface.co/docs/datasets/access": "Know Your Dataset",
                "https://huggingface.co/docs/datasets/use_dataset": "Use a Dataset",
                "https://huggingface.co/docs/datasets/about_arrow": "About Arrow",
                "https://huggingface.co/docs/datasets/about_cache": "About Cache",
                "https://huggingface.co/docs/datasets/about_mapstyle_vs_iterable": "Map-style vs Iterable",
            },
        },
        "datasets-processing": {
            "pages": {
                "https://huggingface.co/docs/datasets/process": "Process",
                "https://huggingface.co/docs/datasets/stream": "Stream",
                "https://huggingface.co/docs/datasets/use_with_pytorch": "Use with PyTorch",
                "https://huggingface.co/docs/datasets/use_with_tensorflow": "Use with TensorFlow",
                "https://huggingface.co/docs/datasets/use_with_jax": "Use with JAX",
                "https://huggingface.co/docs/datasets/use_with_spark": "Use with Spark",
                "https://huggingface.co/docs/datasets/audio_process": "Audio Processing",
                "https://huggingface.co/docs/datasets/image_process": "Image Processing",
                "https://huggingface.co/docs/datasets/nlp_process": "NLP Processing",
                "https://huggingface.co/docs/datasets/tabular_load": "Tabular Data",
                "https://huggingface.co/docs/datasets/how_to_create": "Create a Dataset",
                "https://huggingface.co/docs/datasets/upload_dataset": "Share a Dataset",
            },
        },
        "datasets-metrics": {
            "pages": {
                "https://huggingface.co/docs/datasets/how_to_metrics": "How to Use Metrics",
                "https://huggingface.co/docs/datasets/about_metrics": "About Metrics",
            },
        },
        "datasets-dataset-card": {
            "pages": {
                "https://huggingface.co/docs/datasets/dataset_card": "Dataset Card",
                "https://huggingface.co/docs/datasets/repository_structure": "Repository Structure",
            },
        },
        "diffusers-quicktour": {
            "pages": {
                "https://huggingface.co/docs/diffusers/index": "Diffusers Documentation",
                "https://huggingface.co/docs/diffusers/quicktour": "Quick Tour",
                "https://huggingface.co/docs/diffusers/installation": "Installation",
                "https://huggingface.co/docs/diffusers/stable_diffusion": "Effective and Efficient Diffusion",
            },
        },
        "diffusers-basic-training": {
            "pages": {
                "https://huggingface.co/docs/diffusers/tutorials/basic_training": "Basic Training",
                "https://huggingface.co/docs/diffusers/training/overview": "Training Overview",
                "https://huggingface.co/docs/diffusers/training/unconditional_training": "Unconditional Image Generation",
                "https://huggingface.co/docs/diffusers/training/text2image": "Text-to-Image Training",
                "https://huggingface.co/docs/diffusers/training/lora": "LoRA Training",
                "https://huggingface.co/docs/diffusers/training/dreambooth": "DreamBooth",
                "https://huggingface.co/docs/diffusers/training/textual_inversion": "Textual Inversion",
                "https://huggingface.co/docs/diffusers/training/controlnet": "ControlNet Training",
                "https://huggingface.co/docs/diffusers/training/instructpix2pix": "InstructPix2Pix",
            },
        },
        "diffusers-stable-diffusion": {
            "pages": {
                "https://huggingface.co/docs/diffusers/using-diffusers/loading": "Loading Pipelines",
                "https://huggingface.co/docs/diffusers/using-diffusers/schedulers": "Schedulers",
                "https://huggingface.co/docs/diffusers/using-diffusers/write_own_pipeline": "Write Your Own Pipeline",
                "https://huggingface.co/docs/diffusers/using-diffusers/img2img": "Image-to-Image",
                "https://huggingface.co/docs/diffusers/using-diffusers/inpaint": "Inpainting",
                "https://huggingface.co/docs/diffusers/using-diffusers/depth2img": "Depth-to-Image",
                "https://huggingface.co/docs/diffusers/using-diffusers/controlnet": "ControlNet",
                "https://huggingface.co/docs/diffusers/using-diffusers/weighted_prompts": "Weighted Prompts",
                "https://huggingface.co/docs/diffusers/using-diffusers/callback": "Callbacks",
                "https://huggingface.co/docs/diffusers/optimization/fp16": "FP16 Optimization",
                "https://huggingface.co/docs/diffusers/optimization/torch2.0": "PyTorch 2.0 Optimization",
                "https://huggingface.co/docs/diffusers/optimization/xformers": "xFormers Optimization",
                "https://huggingface.co/docs/diffusers/api/pipelines/stable_diffusion/overview": "Stable Diffusion Pipeline",
                "https://huggingface.co/docs/diffusers/api/pipelines/stable_diffusion/text2img": "Text-to-Image Pipeline",
                "https://huggingface.co/docs/diffusers/api/pipelines/stable_diffusion/img2img": "Image-to-Image Pipeline",
                "https://huggingface.co/docs/diffusers/api/pipelines/stable_diffusion/inpaint": "Inpainting Pipeline",
                "https://huggingface.co/docs/diffusers/api/pipelines/stable_diffusion_xl": "SDXL Pipeline",
            },
        },
        "hub-repositories": {
            "pages": {
                "https://huggingface.co/docs/hub/index": "Hub Documentation",
                "https://huggingface.co/docs/hub/repositories": "Repositories",
                "https://huggingface.co/docs/hub/repositories-getting-started": "Getting Started with Repositories",
                "https://huggingface.co/docs/hub/repositories-settings": "Repository Settings",
                "https://huggingface.co/docs/hub/repositories-pull-requests-discussions": "Pull Requests & Discussions",
                "https://huggingface.co/docs/hub/repositories-next-steps": "Next Steps",
                "https://huggingface.co/docs/hub/repositories-licenses": "Licenses",
            },
        },
        "hub-models": {
            "pages": {
                "https://huggingface.co/docs/hub/models": "Models",
                "https://huggingface.co/docs/hub/models-the-hub": "The Model Hub",
                "https://huggingface.co/docs/hub/models-uploading": "Uploading Models",
                "https://huggingface.co/docs/hub/models-downloading": "Downloading Models",
                "https://huggingface.co/docs/hub/models-libraries": "Libraries",
                "https://huggingface.co/docs/hub/models-tasks": "Tasks",
                "https://huggingface.co/docs/hub/models-widgets": "Widgets",
                "https://huggingface.co/docs/hub/models-inference": "Inference API",
                "https://huggingface.co/docs/hub/model-cards": "Model Cards",
                "https://huggingface.co/docs/hub/models-gated": "Gated Models",
            },
        },
        "hub-datasets": {
            "pages": {
                "https://huggingface.co/docs/hub/datasets": "Datasets on the Hub",
                "https://huggingface.co/docs/hub/datasets-overview": "Datasets Overview",
                "https://huggingface.co/docs/hub/datasets-adding": "Adding Datasets",
                "https://huggingface.co/docs/hub/datasets-viewer": "Datasets Viewer",
                "https://huggingface.co/docs/hub/datasets-download-stats": "Download Stats",
                "https://huggingface.co/docs/hub/datasets-data-files-configuration": "Data Files Configuration",
            },
        },
        "hub-spaces": {
            "pages": {
                "https://huggingface.co/docs/hub/spaces": "Spaces",
                "https://huggingface.co/docs/hub/spaces-overview": "Spaces Overview",
                "https://huggingface.co/docs/hub/spaces-sdks-gradio": "Gradio Spaces",
                "https://huggingface.co/docs/hub/spaces-sdks-streamlit": "Streamlit Spaces",
                "https://huggingface.co/docs/hub/spaces-sdks-docker": "Docker Spaces",
                "https://huggingface.co/docs/hub/spaces-sdks-static": "Static Spaces",
                "https://huggingface.co/docs/hub/spaces-config-reference": "Configuration Reference",
                "https://huggingface.co/docs/hub/spaces-embed": "Embedding Spaces",
                "https://huggingface.co/docs/hub/spaces-gpu": "GPU Spaces",
                "https://huggingface.co/docs/hub/spaces-changelog": "Changelog",
            },
        },
        "hub-webhooks": {
            "pages": {
                "https://huggingface.co/docs/hub/webhooks": "Webhooks",
                "https://huggingface.co/docs/hub/webhooks-guide": "Webhooks Guide",
            },
        },
        "peft-quicktour": {
            "pages": {
                "https://huggingface.co/docs/peft/index": "PEFT Documentation",
                "https://huggingface.co/docs/peft/quicktour": "Quick Tour",
                "https://huggingface.co/docs/peft/install": "Installation",
            },
        },
        "peft-lora": {
            "pages": {
                "https://huggingface.co/docs/peft/conceptual_guides/lora": "LoRA Conceptual Guide",
                "https://huggingface.co/docs/peft/task_guides/clm-lora": "Causal LM with LoRA",
                "https://huggingface.co/docs/peft/task_guides/seq2seq-lora": "Seq2Seq with LoRA",
                "https://huggingface.co/docs/peft/task_guides/image_classification_lora": "Image Classification with LoRA",
                "https://huggingface.co/docs/peft/task_guides/token-classification-lora": "Token Classification with LoRA",
                "https://huggingface.co/docs/peft/developer_guides/lora": "LoRA Developer Guide",
            },
        },
        "peft-adapters": {
            "pages": {
                "https://huggingface.co/docs/peft/conceptual_guides/adapter": "Adapters Conceptual Guide",
                "https://huggingface.co/docs/peft/conceptual_guides/ia3": "IA3",
                "https://huggingface.co/docs/peft/conceptual_guides/prompting": "Prompt Tuning",
                "https://huggingface.co/docs/peft/developer_guides/quantization": "Quantization",
                "https://huggingface.co/docs/peft/developer_guides/model_merging": "Model Merging",
                "https://huggingface.co/docs/peft/developer_guides/troubleshooting": "Troubleshooting",
                "https://huggingface.co/docs/peft/developer_guides/custom_models": "Custom Models",
                "https://huggingface.co/docs/peft/package_reference/peft_model": "PeftModel",
                "https://huggingface.co/docs/peft/package_reference/config": "PeftConfig",
                "https://huggingface.co/docs/peft/package_reference/lora": "LoraConfig",
            },
        },
        "accelerate": {
            "pages": {
                "https://huggingface.co/docs/accelerate/index": "Accelerate Documentation",
                "https://huggingface.co/docs/accelerate/quicktour": "Quick Tour",
                "https://huggingface.co/docs/accelerate/installation": "Installation",
                "https://huggingface.co/docs/accelerate/basic_tutorials/overview": "Overview",
                "https://huggingface.co/docs/accelerate/basic_tutorials/migration": "Migration from PyTorch",
                "https://huggingface.co/docs/accelerate/basic_tutorials/launch": "Launching Scripts",
                "https://huggingface.co/docs/accelerate/basic_tutorials/notebook": "Notebook Launcher",
                "https://huggingface.co/docs/accelerate/concept_guides/deferring_execution": "Deferring Execution",
                "https://huggingface.co/docs/accelerate/concept_guides/gradient_synchronization": "Gradient Synchronization",
                "https://huggingface.co/docs/accelerate/concept_guides/big_model_inference": "Big Model Inference",
                "https://huggingface.co/docs/accelerate/concept_guides/fsdp_and_deepspeed": "FSDP and DeepSpeed",
                "https://huggingface.co/docs/accelerate/usage_guides/deepspeed": "DeepSpeed",
                "https://huggingface.co/docs/accelerate/usage_guides/fsdp": "FSDP",
                "https://huggingface.co/docs/accelerate/usage_guides/megatron_lm": "Megatron-LM",
                "https://huggingface.co/docs/accelerate/usage_guides/checkpoint": "Checkpointing",
                "https://huggingface.co/docs/accelerate/usage_guides/tracking": "Experiment Tracking",
                "https://huggingface.co/docs/accelerate/usage_guides/gradient_accumulation": "Gradient Accumulation",
                "https://huggingface.co/docs/accelerate/usage_guides/local_sgd": "Local SGD",
                "https://huggingface.co/docs/accelerate/usage_guides/quantization": "Quantization",
                "https://huggingface.co/docs/accelerate/package_reference/accelerator": "Accelerator",
            },
        },
        "tokenizers": {
            "pages": {
                "https://huggingface.co/docs/tokenizers/index": "Tokenizers Documentation",
                "https://huggingface.co/docs/tokenizers/quicktour": "Quick Tour",
                "https://huggingface.co/docs/tokenizers/installation": "Installation",
                "https://huggingface.co/docs/tokenizers/pipeline": "The Tokenization Pipeline",
                "https://huggingface.co/docs/tokenizers/components": "Components",
                "https://huggingface.co/docs/tokenizers/training_from_memory": "Training from Memory",
                "https://huggingface.co/docs/tokenizers/api/tokenizer": "Tokenizer API",
                "https://huggingface.co/docs/tokenizers/api/models": "Models API",
                "https://huggingface.co/docs/tokenizers/api/pre-tokenizers": "Pre-tokenizers API",
                "https://huggingface.co/docs/tokenizers/api/post-processors": "Post-processors API",
                "https://huggingface.co/docs/tokenizers/api/trainers": "Trainers API",
                "https://huggingface.co/docs/tokenizers/api/encode-inputs": "Encode Inputs API",
                "https://huggingface.co/docs/tokenizers/api/encoding": "Encoding API",
                "https://huggingface.co/docs/tokenizers/api/normalizers": "Normalizers API",
                "https://huggingface.co/docs/tokenizers/api/decoders": "Decoders API",
            },
        },
        "evaluate": {
            "pages": {
                "https://huggingface.co/docs/evaluate/index": "Evaluate Documentation",
                "https://huggingface.co/docs/evaluate/installation": "Installation",
                "https://huggingface.co/docs/evaluate/a_quick_tour": "Quick Tour",
                "https://huggingface.co/docs/evaluate/types_of_evaluations": "Types of Evaluations",
                "https://huggingface.co/docs/evaluate/choosing_a_metric": "Choosing a Metric",
                "https://huggingface.co/docs/evaluate/custom_evaluator": "Custom Evaluator",
                "https://huggingface.co/docs/evaluate/transformers_integrations": "Transformers Integration",
                "https://huggingface.co/docs/evaluate/base_evaluator": "Evaluator",
                "https://huggingface.co/docs/evaluate/package_reference/main_classes": "Main Classes",
                "https://huggingface.co/docs/evaluate/package_reference/loading_methods": "Loading Methods",
                "https://huggingface.co/docs/evaluate/package_reference/hub_methods": "Hub Methods",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"huggingface-{source_key}" if source_key else "huggingface"
        super().__init__(name, base_dir, interval_seconds=3600)
        self.source_key = source_key

    def _strip_html(self, html_content):
        """Remove HTML tags, scripts, styles and normalize whitespace."""
        text = html_content
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<nav[^>]*>.*?</nav>', '', text, flags=re.DOTALL)
        text = re.sub(r'<footer[^>]*>.*?</footer>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = html_mod.unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _extract_title(self, html_content, fallback):
        """Extract page title from HTML."""
        match = re.search(r'<title>([^<]+)</title>', html_content, re.IGNORECASE)
        if match:
            title = match.group(1).strip()
            # Clean common suffixes
            for suffix in [' - Hugging Face', ' Hugging Face', ' | Hugging Face']:
                if title.endswith(suffix):
                    title = title[:-len(suffix)].strip()
            return title
        return fallback

    def _scrape_source(self, source_key, config):
        """Scrape all pages for a given source section."""
        count = 0
        pages = config.get("pages", {})

        for url, title in pages.items():
            if not self.running:
                break

            item_id = self.make_id(url)
            content = self.fetch_url(url)

            if content and len(content) > 500:
                text = self._strip_html(content)
                if len(text) > 100:
                    page_title = self._extract_title(content, title)

                    if self.save_item(item_id, {
                        "title": page_title,
                        "content": text[:50000],
                        "url": url,
                        "category": f"huggingface-{source_key}",
                        "type": "documentation",
                    }):
                        count += 1
                        self.log.info(f"  {source_key}: {title}")

            time.sleep(2.0)  # Respectful rate limit for documentation site

        return count

    def scrape(self):
        """Run scrape across all or a specific source."""
        total = 0

        if self.source_key:
            if self.source_key not in self.SOURCES:
                self.log.error(
                    f"Unknown source key: {self.source_key}. "
                    f"Available: {list(self.SOURCES.keys())}"
                )
                return 0
            sources = {self.source_key: self.SOURCES[self.source_key]}
        else:
            sources = self.SOURCES

        for key, config in sources.items():
            if not self.running:
                break
            self.log.info(f"=== Scraping huggingface/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    HuggingFaceScraper(base, source_key).run()
