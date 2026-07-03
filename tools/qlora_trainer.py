#!/usr/bin/env python3
"""
QLoRA Fine-Tuning on CPU (GPU-Free Learning)

Trains lightweight adapters on frozen models using 4-bit quantization.
Designed to run on CPU with minimal RAM (5-8GB).

Usage:
    python3 qlora_trainer.py --model mistral-7b --task debugging --examples 1000
"""

import torch
import psycopg2
import json
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class QLoRAConfig:
    """Configuration for QLoRA training"""

    # Model settings
    base_model: str = "mistralai/Mistral-7B-Instruct-v0.2"
    load_in_4bit: bool = True  # 4-bit quantization

    # LoRA settings
    lora_r: int = 8  # Rank (higher = more capacity, more memory)
    lora_alpha: int = 16  # Scaling factor
    lora_dropout: float = 0.05
    target_modules: List[str] = None  # Auto-detect

    # Training settings
    learning_rate: float = 2e-4
    num_epochs: int = 3
    batch_size: int = 1  # CPU-friendly
    gradient_accumulation_steps: int = 4  # Effective batch=4
    max_seq_length: int = 512

    # Hardware settings
    device: str = "cpu"  # Force CPU
    use_cpu: bool = True
    num_cpu_threads: int = 8

    # Output
    output_dir: str = "~/fine-tuning/qlora-checkpoints"
    save_steps: int = 100

    def __post_init__(self):
        if self.target_modules is None:
            # Auto-detect LoRA targets for Mistral
            self.target_modules = ["q_proj", "v_proj", "k_proj", "o_proj"]


class QLoRATrainer:
    """
    CPU-friendly QLoRA fine-tuning

    Key optimizations:
    - 4-bit quantization (3.5GB model instead of 14GB)
    - Small LoRA rank (32MB adapter instead of 7GB)
    - Batch size 1 (minimal memory)
    - CPU-optimized operations
    """

    def __init__(self, config: QLoRAConfig):
        self.config = config
        self.model = None
        self.tokenizer = None
        self.peft_model = None

    def setup_cpu_optimization(self):
        """Optimize for CPU training"""

        # Set CPU threads
        torch.set_num_threads(self.config.num_cpu_threads)

        # Disable CUDA (force CPU)
        import os
        os.environ["CUDA_VISIBLE_DEVICES"] = ""

        logger.info(f"CPU optimization: {self.config.num_cpu_threads} threads")

    def load_model_and_tokenizer(self):
        """Load base model with 4-bit quantization"""

        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        except ImportError:
            logger.error("Missing dependencies. Install with:")
            logger.error("  pip install transformers bitsandbytes peft accelerate")
            raise

        logger.info(f"Loading {self.config.base_model} with 4-bit quantization...")

        # Quantization config
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",  # Normal Float 4-bit
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True  # Nested quantization for extra compression
        )

        # Load model (quantized)
        self.model = AutoModelForCausalLM.from_pretrained(
            self.config.base_model,
            quantization_config=bnb_config,
            device_map="cpu",  # Force CPU
            trust_remote_code=True,
            low_cpu_mem_usage=True
        )

        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.config.base_model,
            trust_remote_code=True
        )

        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        logger.info(f"✓ Model loaded: ~{self._estimate_memory():.1f}GB RAM")

    def prepare_lora_model(self):
        """Add LoRA adapters to frozen model"""

        try:
            from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
        except ImportError:
            logger.error("Missing PEFT library. Install: pip install peft")
            raise

        logger.info("Preparing LoRA adapters...")

        # Prepare for k-bit training
        self.model = prepare_model_for_kbit_training(self.model)

        # LoRA config
        lora_config = LoraConfig(
            r=self.config.lora_r,
            lora_alpha=self.config.lora_alpha,
            target_modules=self.config.target_modules,
            lora_dropout=self.config.lora_dropout,
            bias="none",
            task_type="CAUSAL_LM"
        )

        # Add LoRA layers
        self.peft_model = get_peft_model(self.model, lora_config)

        # Print trainable parameters
        trainable_params = sum(p.numel() for p in self.peft_model.parameters() if p.requires_grad)
        total_params = sum(p.numel() for p in self.peft_model.parameters())

        logger.info(f"✓ LoRA adapters added:")
        logger.info(f"  Trainable params: {trainable_params:,} ({trainable_params/total_params*100:.2f}%)")
        logger.info(f"  Frozen params: {total_params - trainable_params:,}")

    def load_training_data_from_postgres(self, task_type: str, limit: int = 1000) -> List[Dict]:
        """Load training examples from PostgreSQL"""

        logger.info(f"Loading training data for '{task_type}' from PostgreSQL...")

        try:
            conn = psycopg2.connect(
                host='aio-01',
                port=5433,
                user='sfloess',
                database='learning'
            )
            cursor = conn.cursor()

            # Query successful task executions
            cursor.execute("""
                SELECT
                    task_description,
                    solution,
                    quality_score
                FROM learning.task_executions
                WHERE task_type = %s
                  AND quality_score > 0.7
                  AND solution IS NOT NULL
                ORDER BY quality_score DESC
                LIMIT %s
            """, (task_type, limit))

            examples = []
            for row in cursor.fetchall():
                examples.append({
                    'task': row[0],
                    'solution': row[1],
                    'quality': row[2]
                })

            cursor.close()
            conn.close()

            logger.info(f"✓ Loaded {len(examples)} training examples")
            return examples

        except Exception as e:
            logger.warning(f"PostgreSQL query failed: {e}")
            logger.info("Falling back to synthetic examples...")
            return self._generate_synthetic_examples(task_type, limit)

    def _generate_synthetic_examples(self, task_type: str, limit: int) -> List[Dict]:
        """Generate synthetic training examples (fallback)"""

        # Placeholder - in real use, load from files or generate
        logger.warning("Using synthetic examples - not ideal for production!")

        examples = []
        for i in range(min(limit, 100)):
            examples.append({
                'task': f"Example {task_type} task {i}",
                'solution': f"Solution for task {i}",
                'quality': 0.8
            })

        return examples

    def format_training_data(self, examples: List[Dict]) -> List[Dict]:
        """Format examples for instruction tuning"""

        formatted = []
        for ex in examples:
            # Instruction format
            prompt = f"### Task:\n{ex['task']}\n\n### Solution:\n"
            completion = ex['solution']

            formatted.append({
                'input': prompt,
                'output': completion
            })

        return formatted

    def train(self, training_data: List[Dict]):
        """Train LoRA adapters"""

        try:
            from transformers import Trainer, TrainingArguments, DataCollatorForLanguageModeling
            from datasets import Dataset
        except ImportError:
            logger.error("Missing transformers/datasets. Install: pip install transformers datasets")
            raise

        logger.info(f"Starting training on {len(training_data)} examples...")

        # Convert to Dataset
        dataset = Dataset.from_list(training_data)

        # Tokenize
        def tokenize_function(examples):
            full_text = [inp + out for inp, out in zip(examples['input'], examples['output'])]
            return self.tokenizer(
                full_text,
                truncation=True,
                max_length=self.config.max_seq_length,
                padding="max_length"
            )

        tokenized_dataset = dataset.map(
            tokenize_function,
            batched=True,
            remove_columns=dataset.column_names
        )

        # Training arguments
        output_dir = Path(self.config.output_dir).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)

        training_args = TrainingArguments(
            output_dir=str(output_dir),
            num_train_epochs=self.config.num_epochs,
            per_device_train_batch_size=self.config.batch_size,
            gradient_accumulation_steps=self.config.gradient_accumulation_steps,
            learning_rate=self.config.learning_rate,
            fp16=False,  # CPU doesn't support fp16
            logging_steps=10,
            save_steps=self.config.save_steps,
            save_total_limit=3,
            no_cuda=True,  # Force CPU
            dataloader_num_workers=0,  # CPU-friendly
            report_to="none"
        )

        # Data collator
        data_collator = DataCollatorForLanguageModeling(
            tokenizer=self.tokenizer,
            mlm=False
        )

        # Trainer
        trainer = Trainer(
            model=self.peft_model,
            args=training_args,
            train_dataset=tokenized_dataset,
            data_collator=data_collator
        )

        # Train!
        logger.info("Training started... (this will take 12-24 hours on CPU)")
        trainer.train()

        # Save final model
        final_path = output_dir / "final"
        self.peft_model.save_pretrained(str(final_path))
        self.tokenizer.save_pretrained(str(final_path))

        logger.info(f"✅ Training complete! Model saved to {final_path}")

    def _estimate_memory(self) -> float:
        """Estimate RAM usage in GB"""
        if self.model is None:
            return 0.0

        # 4-bit model ≈ 3.5GB for 7B params
        base_memory = 3.5

        # LoRA adapters ≈ 32MB
        lora_memory = 0.032

        # Training overhead ≈ 2GB
        training_memory = 2.0

        return base_memory + lora_memory + training_memory


def main():
    """Main training script"""
    import argparse

    parser = argparse.ArgumentParser(description="QLoRA CPU Fine-Tuning")
    parser.add_argument("--model", default="mistralai/Mistral-7B-Instruct-v0.2")
    parser.add_argument("--task", default="debugging", help="Task type to train on")
    parser.add_argument("--examples", type=int, default=1000)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--output", default="~/fine-tuning/qlora-checkpoints")

    args = parser.parse_args()

    # Config
    config = QLoRAConfig(
        base_model=args.model,
        num_epochs=args.epochs,
        output_dir=args.output
    )

    # Trainer
    trainer = QLoRATrainer(config)

    # Setup
    trainer.setup_cpu_optimization()
    trainer.load_model_and_tokenizer()
    trainer.prepare_lora_model()

    # Load data
    examples = trainer.load_training_data_from_postgres(args.task, args.examples)
    training_data = trainer.format_training_data(examples)

    # Train
    trainer.train(training_data)

    logger.info("✅ QLoRA training complete!")


if __name__ == '__main__':
    main()
