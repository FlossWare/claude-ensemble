
import pickle
import pandas as pd
from pathlib import Path

# Load the predictor
predictor_path = Path.home() / '.claude' / 'learning' / 'predictors' / 'memory-usage-predictor.pkl'
with open(predictor_path, 'rb') as f:
    data = pickle.load(f)
    model = data['model']
    metadata = data['metadata']

# Prepare input features
# Example: 6 opus workers, 5000 input tokens, 2000 output tokens
features = {
    'input_tokens': 5000,
    'output_tokens': 2000,
    'total_tokens': 7000,
    'worker_count': 6,
    # Model one-hot encoding (set your model to 1, others to 0)
    'model_opus': 1,
    'model_sonnet': 0,
    'model_haiku': 0,
    # ... (add all other model features from metadata['features'])
}

# Create DataFrame with correct feature order
X = pd.DataFrame([features])
# Ensure all features from training are present
for feature in metadata['features']:
    if feature not in X.columns:
        X[feature] = 0

# Reorder columns to match training
X = X[metadata['features']]

# Predict memory usage
predicted_memory_mb = model.predict(X)[0]
print(f"Predicted Peak Memory: {predicted_memory_mb:.1f} MB ({predicted_memory_mb/1024:.2f} GB)")

# Use prediction to prevent OOM
MAX_AVAILABLE_RAM_MB = 107 * 1024  # 107 GB
if predicted_memory_mb > MAX_AVAILABLE_RAM_MB * 0.8:
    print(f"WARNING: Predicted usage ({predicted_memory_mb/1024:.1f} GB) exceeds 80% of available RAM")
    print("Consider reducing worker_count or batch size")
