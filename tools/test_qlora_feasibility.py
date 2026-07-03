#!/usr/bin/env python3
"""
Test QLoRA Feasibility on CPU

Quick test to determine:
1. Can we load 4-bit quantized model?
2. How much RAM does it use?
3. How long does training take?
4. Is CPU fast enough?

Run this FIRST before committing to 24-hour training!
"""

import sys
import time
import psutil
import platform
from pathlib import Path

def check_dependencies():
    """Check if required packages installed"""

    print("=" * 60)
    print("DEPENDENCY CHECK")
    print("=" * 60)
    print()

    required = {
        'torch': 'torch',
        'transformers': 'transformers',
        'peft': 'peft',
        'bitsandbytes': 'bitsandbytes',
        'accelerate': 'accelerate'
    }

    missing = []
    for name, package in required.items():
        try:
            __import__(package)
            print(f"✓ {name}")
        except ImportError:
            print(f"✗ {name} (missing)")
            missing.append(package)

    print()

    if missing:
        print("Install missing packages:")
        print(f"  pip install {' '.join(missing)}")
        return False

    return True


def check_system_resources():
    """Check CPU, RAM, disk"""

    print("=" * 60)
    print("SYSTEM RESOURCES")
    print("=" * 60)
    print()

    # CPU
    cpu_count = psutil.cpu_count()
    cpu_freq = psutil.cpu_freq()
    print(f"CPU:")
    print(f"  Cores: {cpu_count}")
    if cpu_freq:
        print(f"  Frequency: {cpu_freq.current:.0f} MHz")
    print(f"  Model: {platform.processor()}")
    print()

    # RAM
    ram = psutil.virtual_memory()
    print(f"RAM:")
    print(f"  Total: {ram.total / 1024**3:.1f} GB")
    print(f"  Available: {ram.available / 1024**3:.1f} GB")
    print(f"  Used: {ram.percent}%")
    print()

    # Disk
    disk = psutil.disk_usage(str(Path.home()))
    print(f"Disk (home):")
    print(f"  Total: {disk.total / 1024**3:.1f} GB")
    print(f"  Free: {disk.free / 1024**3:.1f} GB")
    print()

    # Check minimums
    warnings = []
    if ram.available < 8 * 1024**3:
        warnings.append(f"⚠️  Low RAM: {ram.available / 1024**3:.1f}GB (need 8GB)")

    if disk.free < 20 * 1024**3:
        warnings.append(f"⚠️  Low disk: {disk.free / 1024**3:.1f}GB (need 20GB)")

    if warnings:
        print("WARNINGS:")
        for w in warnings:
            print(f"  {w}")
        print()

    return len(warnings) == 0


def test_model_loading():
    """Test loading quantized model"""

    print("=" * 60)
    print("MODEL LOADING TEST")
    print("=" * 60)
    print()

    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

        print("Loading tiny model for testing (TinyLlama-1.1B)...")
        print("(Using small model to test quickly)")
        print()

        model_name = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"

        # 4-bit config
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True
        )

        start_ram = psutil.virtual_memory().used / 1024**3
        start_time = time.time()

        # Load model
        print("Loading model (this may take 2-3 minutes)...")
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            quantization_config=bnb_config,
            device_map="cpu",
            trust_remote_code=True,
            low_cpu_mem_usage=True
        )

        tokenizer = AutoTokenizer.from_pretrained(model_name)

        load_time = time.time() - start_time
        end_ram = psutil.virtual_memory().used / 1024**3
        ram_used = end_ram - start_ram

        print(f"✓ Model loaded successfully!")
        print(f"  Load time: {load_time:.1f}s")
        print(f"  RAM used: {ram_used:.1f}GB")
        print()

        # Test inference
        print("Testing inference...")
        test_prompt = "Hello, how are you?"
        inputs = tokenizer(test_prompt, return_tensors="pt")

        start_time = time.time()
        outputs = model.generate(**inputs, max_new_tokens=20)
        inference_time = time.time() - start_time

        response = tokenizer.decode(outputs[0], skip_special_tokens=True)

        print(f"✓ Inference working!")
        print(f"  Time: {inference_time:.1f}s for 20 tokens")
        print(f"  Speed: {20/inference_time:.1f} tokens/sec")
        print()

        # Estimate for Mistral-7B
        print("ESTIMATE FOR MISTRAL-7B:")
        # TinyLlama = 1.1B params, Mistral = 7B params (6.4× larger)
        estimated_ram = ram_used * 6.4
        estimated_load_time = load_time * 6.4

        print(f"  Estimated RAM: {estimated_ram:.1f}GB")
        print(f"  Estimated load time: {estimated_load_time/60:.1f} minutes")
        print()

        if estimated_ram > psutil.virtual_memory().available / 1024**3:
            print("⚠️  WARNING: Mistral-7B may not fit in available RAM!")
            print(f"     Need: {estimated_ram:.1f}GB")
            print(f"     Have: {psutil.virtual_memory().available / 1024**3:.1f}GB")
            return False

        return True

    except Exception as e:
        print(f"✗ Model loading failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_training_speed():
    """Estimate training time"""

    print("=" * 60)
    print("TRAINING SPEED TEST")
    print("=" * 60)
    print()

    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

        print("Testing training speed with TinyLlama...")
        print()

        model_name = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"

        # Load model (reuse if already loaded)
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16
        )

        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            quantization_config=bnb_config,
            device_map="cpu",
            low_cpu_mem_usage=True
        )

        tokenizer = AutoTokenizer.from_pretrained(model_name)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        # Add LoRA
        model = prepare_model_for_kbit_training(model)

        lora_config = LoraConfig(
            r=8,
            lora_alpha=16,
            target_modules=["q_proj", "v_proj"],
            lora_dropout=0.05,
            bias="none",
            task_type="CAUSAL_LM"
        )

        model = get_peft_model(model, lora_config)

        print("✓ LoRA model prepared")
        print()

        # Simulate one training step
        print("Running 10 training steps (simulation)...")

        optimizer = torch.optim.AdamW(model.parameters(), lr=2e-4)

        total_time = 0
        for i in range(10):
            # Prepare fake batch
            inputs = tokenizer("Example training text " * 50, return_tensors="pt", max_length=128, truncation=True)
            labels = inputs["input_ids"].clone()

            start = time.time()

            # Forward pass
            outputs = model(**inputs, labels=labels)
            loss = outputs.loss

            # Backward pass
            loss.backward()
            optimizer.step()
            optimizer.zero_grad()

            step_time = time.time() - start
            total_time += step_time

            print(f"  Step {i+1}/10: {step_time:.1f}s")

        avg_step_time = total_time / 10

        print()
        print(f"✓ Average step time: {avg_step_time:.1f}s")
        print()

        # Estimate for full training
        print("ESTIMATE FOR FULL TRAINING:")

        # Typical training: 1000 examples, batch size 1, 3 epochs = 3000 steps
        total_steps = 3000

        # TinyLlama vs Mistral-7B: Mistral is 6.4× larger, ~6.4× slower per step
        mistral_step_time = avg_step_time * 6.4

        estimated_hours = (total_steps * mistral_step_time) / 3600

        print(f"  Steps needed: {total_steps}")
        print(f"  Estimated step time (Mistral-7B): {mistral_step_time:.1f}s")
        print(f"  Estimated total time: {estimated_hours:.1f} hours")
        print()

        if estimated_hours > 48:
            print("⚠️  WARNING: Training will take > 2 days!")
            print("     Consider using cloud GPU instead")
            return False
        elif estimated_hours > 24:
            print("⚠️  WARNING: Training will take > 1 day")
            print("     Acceptable but slow")
            return True
        else:
            print("✓ Training time acceptable (< 24 hours)")
            return True

    except Exception as e:
        print(f"✗ Training test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all feasibility tests"""

    print()
    print("QLoRA CPU FEASIBILITY TEST")
    print("Testing if CPU training is viable on this system")
    print()

    results = {
        'dependencies': False,
        'resources': False,
        'model_loading': False,
        'training_speed': False
    }

    # Run tests
    results['dependencies'] = check_dependencies()

    if not results['dependencies']:
        print("\n❌ STOP: Install dependencies first\n")
        return 1

    results['resources'] = check_system_resources()
    results['model_loading'] = test_model_loading()

    if results['model_loading']:
        results['training_speed'] = test_training_speed()

    # Summary
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print()

    for test, passed in results.items():
        status = "✓" if passed else "✗"
        print(f"{status} {test.replace('_', ' ').title()}")

    print()

    if all(results.values()):
        print("✅ CPU QLORA IS FEASIBLE!")
        print()
        print("Next steps:")
        print("  1. Prepare training data from PostgreSQL")
        print("  2. Run full training: python3 tools/qlora_trainer.py")
        print("  3. Test fine-tuned model")
        print()
        return 0
    else:
        print("❌ CPU QLORA NOT RECOMMENDED")
        print()
        print("Alternatives:")
        print("  1. Use cloud GPU (Together AI: $1-2)")
        print("  2. Use RunPod (rent GPU: $2-5)")
        print("  3. Use Hugging Face AutoTrain ($2-6)")
        print()
        print("See docs/FINE_TUNING_VENDORS.md for details")
        print()
        return 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
