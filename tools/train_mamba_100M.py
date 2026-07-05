#!/usr/bin/env python3
"""
Train 100M Parameter Mamba Model on CPU
Uses collected training data to build actual LLM

STORAGE: All data on NAS at /mnt/nas/web-scrape/
"""

import os
import json
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from pathlib import Path
import time
from datetime import datetime

# NAS Storage paths
NAS_BASE = Path('/mnt/nas/web-scrape')
DATA_DIR = NAS_BASE / 'synthetic-data'
MODELS_DIR = NAS_BASE / 'models'
LOGS_DIR = NAS_BASE / 'logs'

# Mamba/SSM implementation (simplified)
class MambaBlock(nn.Module):
    """State Space Model block (Mamba architecture)"""

    def __init__(self, d_model=768, d_state=16):
        super().__init__()
        self.d_model = d_model
        self.d_state = d_state

        # Simplified SSM parameters
        self.W_in = nn.Linear(d_model, d_state)
        self.W_out = nn.Linear(d_state, d_model)
        self.layer_norm = nn.LayerNorm(d_model)

    def forward(self, x):
        # Simplified state space computation
        # Real Mamba has selective SSM with hardware-aware algorithms
        batch, seq, dim = x.shape

        # Project to state space
        h = self.W_in(x)  # (batch, seq, d_state)

        # State evolution (simplified recurrence)
        # Real Mamba uses parallel scan
        output = []
        state = torch.zeros(batch, self.d_state, device=x.device)

        for t in range(seq):
            state = 0.9 * state + h[:, t, :]  # Simple state update
            output.append(state)

        h = torch.stack(output, dim=1)  # (batch, seq, d_state)

        # Project back to model dimension
        y = self.W_out(h)

        # Residual connection
        return self.layer_norm(x + y)


class SimpleMamba(nn.Module):
    """100M Parameter Mamba Model"""

    def __init__(self, vocab_size=50000, d_model=768, n_layers=12, d_state=16):
        super().__init__()

        self.vocab_size = vocab_size
        self.d_model = d_model

        # Embedding
        self.token_embedding = nn.Embedding(vocab_size, d_model)
        self.position_embedding = nn.Embedding(2048, d_model)

        # Mamba blocks
        self.blocks = nn.ModuleList([
            MambaBlock(d_model, d_state) for _ in range(n_layers)
        ])

        # Output head
        self.layer_norm = nn.LayerNorm(d_model)
        self.lm_head = nn.Linear(d_model, vocab_size, bias=False)

        print(f"Model initialized: {self.count_parameters():,} parameters")

    def count_parameters(self):
        return sum(p.numel() for p in self.parameters() if p.requires_grad)

    def forward(self, input_ids):
        batch, seq_len = input_ids.shape

        # Embeddings
        positions = torch.arange(seq_len, device=input_ids.device).unsqueeze(0)
        x = self.token_embedding(input_ids) + self.position_embedding(positions)

        # Mamba blocks
        for block in self.blocks:
            x = block(x)

        # Output
        x = self.layer_norm(x)
        logits = self.lm_head(x)

        return logits


class TrainingDataset(Dataset):
    """Load training data from JSONL files"""

    def __init__(self, data_dir, max_length=512):
        self.data_dir = Path(data_dir)
        self.max_length = max_length
        self.examples = []

        # Load all JSONL files
        jsonl_files = list(self.data_dir.glob('*.jsonl'))
        print(f"Loading data from {len(jsonl_files)} files...")

        for file in jsonl_files:
            if file.stat().st_size == 0:
                continue  # Skip empty files

            with open(file) as f:
                for line in f:
                    try:
                        ex = json.loads(line)
                        if 'prompt' in ex and 'completion' in ex:
                            self.examples.append(ex)
                    except:
                        continue

        print(f"Loaded {len(self.examples)} training examples")

    def __len__(self):
        return len(self.examples)

    def __getitem__(self, idx):
        ex = self.examples[idx]

        # Combine prompt and completion
        text = f"Q: {ex['prompt']}\nA: {ex['completion']}"

        # Simple tokenization (character-level for now)
        # Real implementation would use SentencePiece or BPE
        tokens = [ord(c) % 50000 for c in text[:self.max_length]]

        # Pad to max_length
        if len(tokens) < self.max_length:
            tokens += [0] * (self.max_length - len(tokens))

        return torch.tensor(tokens, dtype=torch.long)


def train_model(data_dir, output_dir, epochs=3, batch_size=4, learning_rate=1e-4):
    """Train the model"""

    print("=" * 70)
    print("MAMBA 100M TRAINING")
    print("=" * 70)
    print(f"Data directory: {data_dir}")
    print(f"Output directory: {output_dir}")
    print(f"Epochs: {epochs}")
    print(f"Batch size: {batch_size}")
    print(f"Learning rate: {learning_rate}")
    print("=" * 70)
    print()

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Load dataset
    dataset = TrainingDataset(data_dir)

    if len(dataset) == 0:
        print("❌ No training data found!")
        return

    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True, num_workers=2)

    # Initialize model
    model = SimpleMamba(vocab_size=50000, d_model=768, n_layers=12, d_state=16)

    # Optimizer
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)

    # Loss function
    criterion = nn.CrossEntropyLoss()

    # Training loop
    global_step = 0
    start_time = time.time()

    print(f"\n🔥 TRAINING STARTED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total batches per epoch: {len(dataloader)}")
    print(f"Total training steps: {len(dataloader) * epochs}")
    print()

    for epoch in range(epochs):
        print(f"\n{'='*70}")
        print(f"EPOCH {epoch + 1}/{epochs}")
        print(f"{'='*70}\n")

        model.train()
        epoch_loss = 0.0
        epoch_start = time.time()

        for batch_idx, batch in enumerate(dataloader):
            # Forward pass
            input_ids = batch[:, :-1]  # All but last token
            targets = batch[:, 1:]     # All but first token

            logits = model(input_ids)

            # Reshape for loss calculation
            logits = logits.reshape(-1, model.vocab_size)
            targets = targets.reshape(-1)

            # Compute loss
            loss = criterion(logits, targets)

            # Backward pass
            optimizer.zero_grad()
            loss.backward()

            # Gradient clipping
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)

            optimizer.step()

            # Track loss
            epoch_loss += loss.item()
            global_step += 1

            # Log progress
            if (batch_idx + 1) % 10 == 0:
                avg_loss = epoch_loss / (batch_idx + 1)
                elapsed = time.time() - epoch_start
                steps_per_sec = (batch_idx + 1) / elapsed

                print(f"  Step {global_step:4d} | "
                      f"Batch {batch_idx + 1:3d}/{len(dataloader)} | "
                      f"Loss: {loss.item():.4f} | "
                      f"Avg Loss: {avg_loss:.4f} | "
                      f"Speed: {steps_per_sec:.2f} steps/s")

            # Save checkpoint every 100 steps
            if global_step % 100 == 0:
                checkpoint_path = os.path.join(output_dir, f'checkpoint_step_{global_step}.pt')
                torch.save({
                    'step': global_step,
                    'epoch': epoch,
                    'model_state_dict': model.state_dict(),
                    'optimizer_state_dict': optimizer.state_dict(),
                    'loss': loss.item(),
                }, checkpoint_path)
                print(f"  💾 Checkpoint saved: {checkpoint_path}")

        # End of epoch
        avg_epoch_loss = epoch_loss / len(dataloader)
        epoch_time = time.time() - epoch_start

        print(f"\n  ✅ Epoch {epoch + 1} complete!")
        print(f"     Average loss: {avg_epoch_loss:.4f}")
        print(f"     Time: {epoch_time:.1f}s ({epoch_time/60:.1f} min)")

        # Save epoch checkpoint
        epoch_path = os.path.join(output_dir, f'model_epoch_{epoch + 1}.pt')
        torch.save({
            'epoch': epoch + 1,
            'model_state_dict': model.state_dict(),
            'optimizer_state_dict': optimizer.state_dict(),
            'loss': avg_epoch_loss,
        }, epoch_path)
        print(f"     💾 Saved: {epoch_path}")

    # Training complete
    total_time = time.time() - start_time

    print(f"\n{'='*70}")
    print(f"🎉 TRAINING COMPLETE!")
    print(f"{'='*70}")
    print(f"Total time: {total_time:.1f}s ({total_time/3600:.2f} hours)")
    print(f"Total steps: {global_step}")
    print(f"Final loss: {avg_epoch_loss:.4f}")
    print()

    # Save final model
    final_path = os.path.join(output_dir, 'model_final.pt')
    torch.save({
        'model_state_dict': model.state_dict(),
        'vocab_size': model.vocab_size,
        'd_model': model.d_model,
        'training_examples': len(dataset),
        'epochs': epochs,
    }, final_path)

    print(f"💾 Final model saved: {final_path}")
    print(f"📊 Model size: {os.path.getsize(final_path) / 1024 / 1024:.1f} MB")
    print()
    print("✅ Model is ready for inference!")
    print(f"   Load with: torch.load('{final_path}')")


if __name__ == '__main__':
    import sys

    # NAS Paths (default)
    data_dir = sys.argv[1] if len(sys.argv) > 1 else str(DATA_DIR)
    output_dir = sys.argv[2] if len(sys.argv) > 2 else str(MODELS_DIR / 'mamba-100M')

    print(f"\n🗂️  Using NAS Storage:")
    print(f"   Data: {data_dir}")
    print(f"   Models: {output_dir}\n")

    # Start training
    train_model(
        data_dir=data_dir,
        output_dir=output_dir,
        epochs=3,
        batch_size=4,  # Small batch for CPU
        learning_rate=1e-4
    )
