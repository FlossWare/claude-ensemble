#!/usr/bin/env python3
"""
DISTRIBUTED TRAINING across Fleet
Uses PyTorch Distributed Data Parallel (DDP)
Trains FASTER by using ALL machines!
"""

import os
import sys
import torch
import torch.distributed as dist
import torch.multiprocessing as mp
from torch.nn.parallel import DistributedDataParallel as DDP
from pathlib import Path

# Import the model from existing training script
sys.path.insert(0, str(Path(__file__).parent))
from train_mamba_100M import SimpleMamba, TrainingDataset

# NAS paths
NAS_BASE = Path('/mnt/nas/web-scrape')
DATA_DIR = NAS_BASE / 'synthetic-data'
MODELS_DIR = NAS_BASE / 'models'

def setup_distributed(rank, world_size):
    """Initialize distributed training"""
    os.environ['MASTER_ADDR'] = 'aio-01'  # Coordinator
    os.environ['MASTER_PORT'] = '29500'

    # Initialize process group
    dist.init_process_group(
        backend='gloo',  # Use gloo for CPU (nccl is for GPU)
        init_method='env://',
        world_size=world_size,
        rank=rank
    )

def cleanup_distributed():
    """Clean up distributed training"""
    dist.destroy_process_group()

def train_distributed(rank, world_size, epochs=3):
    """
    Train model in distributed fashion

    Args:
        rank: Worker ID (0 to world_size-1)
        world_size: Total number of workers
    """

    print(f"[Worker {rank}/{world_size}] Starting...")

    # Setup distributed
    setup_distributed(rank, world_size)

    # Load dataset
    dataset = TrainingDataset(str(DATA_DIR))

    # Create distributed sampler
    # Each worker gets a different subset of data
    sampler = torch.utils.data.distributed.DistributedSampler(
        dataset,
        num_replicas=world_size,
        rank=rank,
        shuffle=True
    )

    # DataLoader with distributed sampler
    dataloader = torch.utils.data.DataLoader(
        dataset,
        batch_size=4,
        sampler=sampler,
        num_workers=2
    )

    # Initialize model
    model = SimpleMamba(vocab_size=50000, d_model=768, n_layers=12, d_state=16)

    # Wrap model in DDP
    model = DDP(model)

    # Optimizer
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)

    # Loss
    criterion = torch.nn.CrossEntropyLoss()

    print(f"[Worker {rank}] Training started!")
    print(f"[Worker {rank}] Data samples: {len(dataset) // world_size}")

    # Training loop
    for epoch in range(epochs):
        model.train()
        sampler.set_epoch(epoch)  # Shuffle differently each epoch

        epoch_loss = 0.0

        for batch_idx, batch in enumerate(dataloader):
            # Forward pass
            input_ids = batch[:, :-1]
            targets = batch[:, 1:]

            logits = model(input_ids)

            # Reshape for loss
            logits = logits.reshape(-1, model.module.vocab_size)
            targets = targets.reshape(-1)

            # Compute loss
            loss = criterion(logits, targets)

            # Backward pass
            optimizer.zero_grad()
            loss.backward()

            # Gradient clipping
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)

            optimizer.step()

            epoch_loss += loss.item()

            # Log progress
            if rank == 0 and (batch_idx + 1) % 10 == 0:
                avg_loss = epoch_loss / (batch_idx + 1)
                print(f"[Epoch {epoch+1}/{epochs}] "
                      f"Batch {batch_idx+1}/{len(dataloader)} | "
                      f"Loss: {loss.item():.4f} | "
                      f"Avg: {avg_loss:.4f}")

        # Save checkpoint (only rank 0)
        if rank == 0:
            checkpoint_path = MODELS_DIR / 'mamba-100M-distributed' / f'epoch_{epoch+1}.pt'
            checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

            torch.save({
                'epoch': epoch + 1,
                'model_state_dict': model.module.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'loss': epoch_loss / len(dataloader),
            }, checkpoint_path)

            print(f"[Epoch {epoch+1}] Checkpoint saved: {checkpoint_path}")

    # Cleanup
    cleanup_distributed()

    print(f"[Worker {rank}] Training complete!")


def main():
    """
    Main entry point for distributed training

    Run on each machine:
    ```
    # On aio-01 (rank 0, master):
    python3 train_mamba_distributed.py --rank 0 --world-size 8

    # On server-01 (rank 1):
    python3 train_mamba_distributed.py --rank 1 --world-size 8

    # On server-02 (rank 2):
    python3 train_mamba_distributed.py --rank 2 --world-size 8

    # ... etc for all 8 machines
    ```
    """

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--rank', type=int, required=True, help='Worker rank (0 to world_size-1)')
    parser.add_argument('--world-size', type=int, required=True, help='Total number of workers')
    parser.add_argument('--epochs', type=int, default=3, help='Number of epochs')

    args = parser.parse_args()

    print("="*70)
    print("DISTRIBUTED TRAINING - MAMBA 100M")
    print("="*70)
    print(f"Worker rank: {args.rank} / {args.world_size}")
    print(f"Master: aio-01:29500")
    print(f"Data: {DATA_DIR}")
    print(f"Models: {MODELS_DIR}/mamba-100M-distributed/")
    print("="*70)
    print()

    # Start training
    train_distributed(args.rank, args.world_size, args.epochs)


if __name__ == '__main__':
    main()
