#!/usr/bin/env bash
#
# LAUNCH DISTRIBUTED TRAINING ACROSS FLEET
# Trains a LARGE model using ALL 8 machines!
#

# Fleet configuration
MACHINES=(
    "aio-01"
    "laptop-01"
    "server-01"
    "server-02"
    "server-03"
    "server-ap"
    "desktop-ap"
    "pi-01"
)

# Workers per machine (2 per machine = 16 total workers!)
WORKERS_PER_MACHINE=2
WORLD_SIZE=$((${#MACHINES[@]} * WORKERS_PER_MACHINE))
MASTER="aio-01"
MASTER_PORT="29500"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 DISTRIBUTED TRAINING - LARGE MODEL"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Fleet machines: $WORLD_SIZE"
echo "Master node: $MASTER:$MASTER_PORT"
echo ""

# Ask user which model size
echo "Which model size?"
echo "  1) 1B parameters (RECOMMENDED - uses full fleet)"
echo "  2) 7B parameters (AMBITIOUS - may be tight on RAM)"
echo "  3) 13B parameters (EXPERIMENTAL - distributed required)"
echo ""
read -p "Choice [1]: " choice
choice=${choice:-1}

case $choice in
    1)
        MODEL_SIZE="1B"
        D_MODEL=2048
        N_LAYERS=24
        echo "✅ Training 1B parameter model"
        ;;
    2)
        MODEL_SIZE="7B"
        D_MODEL=4096
        N_LAYERS=32
        echo "✅ Training 7B parameter model"
        ;;
    3)
        MODEL_SIZE="13B"
        D_MODEL=5120
        N_LAYERS=40
        echo "✅ Training 13B parameter model"
        ;;
    *)
        echo "❌ Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "Model configuration:"
echo "  Size: $MODEL_SIZE"
echo "  Embedding dimension: $D_MODEL"
echo "  Layers: $N_LAYERS"
echo "  Workers: $WORLD_SIZE"
echo "  Batch per worker: 4"
echo "  Effective batch: $((4 * WORLD_SIZE))"
echo ""

read -p "Proceed with distributed training? [y/N]: " confirm
if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    echo "Cancelled"
    exit 0
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 LAUNCHING DISTRIBUTED TRAINING"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Stop any existing training
echo "Stopping existing training..."
pkill -f "train_mamba" 2>/dev/null
sleep 2

# Create training script with model size
cat > /tmp/train_distributed_${MODEL_SIZE}.py << 'PYTHON_SCRIPT'
#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'tools'))

# Import and modify for model size
import train_mamba_distributed
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--rank', type=int, required=True)
parser.add_argument('--world-size', type=int, required=True)
parser.add_argument('--d-model', type=int, default=2048)
parser.add_argument('--n-layers', type=int, default=24)
parser.add_argument('--epochs', type=int, default=3)

args = parser.parse_args()

# Modify model creation to use custom size
original_train = train_mamba_distributed.train_distributed

def custom_train(rank, world_size, epochs=3):
    # Override model size
    train_mamba_distributed.SimpleMamba.__init__.__defaults__ = (
        50000,        # vocab_size
        args.d_model, # d_model
        args.n_layers,# n_layers
        16            # d_state
    )
    return original_train(rank, world_size, epochs)

train_mamba_distributed.train_distributed = custom_train
custom_train(args.rank, args.world_size, args.epochs)
PYTHON_SCRIPT

chmod +x /tmp/train_distributed_${MODEL_SIZE}.py

# Launch workers on each machine (2 workers per machine)
global_rank=0

for i in "${!MACHINES[@]}"; do
    machine="${MACHINES[$i]}"

    for local_rank in $(seq 0 $((WORKERS_PER_MACHINE - 1))); do
        rank=$global_rank

        echo "[Rank $rank] Launching on $machine (worker $((local_rank + 1))/$WORKERS_PER_MACHINE)..."

        if [ "$machine" = "$MASTER" ]; then
            # Master node (local)
            MASTER_ADDR=$MASTER MASTER_PORT=$MASTER_PORT \
            python3 /tmp/train_distributed_${MODEL_SIZE}.py \
                --rank $rank \
                --world-size $WORLD_SIZE \
                --d-model $D_MODEL \
                --n-layers $N_LAYERS \
                > /mnt/nas/web-scrape/logs/distributed_rank_${rank}.log 2>&1 &
        else
            # Worker nodes (remote)
            ssh claude@$machine "
                cd ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills && \
                MASTER_ADDR=$MASTER MASTER_PORT=$MASTER_PORT \
                python3 tools/train_mamba_distributed.py \
                    --rank $rank \
                    --world-size $WORLD_SIZE \
                    > /mnt/nas/web-scrape/logs/distributed_rank_${rank}.log 2>&1
            " &
        fi

        ((global_rank++))
        sleep 0.5
    done
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ DISTRIBUTED TRAINING LAUNCHED!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Model: $MODEL_SIZE ($D_MODEL dim, $N_LAYERS layers)"
echo "Workers: $WORLD_SIZE machines"
echo "Effective batch size: $((4 * WORLD_SIZE))"
echo ""
echo "Monitor:"
echo "  Master (rank 0): tail -f /mnt/nas/web-scrape/logs/distributed_rank_0.log"
echo "  All workers:     tail -f /mnt/nas/web-scrape/logs/distributed_rank_*.log"
echo ""
echo "Progress:"
echo "  watch -n 10 'ls -lh /mnt/nas/web-scrape/models/mamba-${MODEL_SIZE}-distributed/'"
echo ""
echo "Estimated time:"
case $MODEL_SIZE in
    "1B")  echo "  ~2-3 days (distributed across $WORLD_SIZE machines)" ;;
    "7B")  echo "  ~5-7 days (distributed across $WORLD_SIZE machines)" ;;
    "13B") echo "  ~10-14 days (distributed across $WORLD_SIZE machines)" ;;
esac
