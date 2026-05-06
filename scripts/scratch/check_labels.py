from transformers import AutoConfig
import sys

model_id = "m3hrdadfi/wav2vec2-large-xlsr-53-spanish-emotion"
try:
    config = AutoConfig.from_pretrained(model_id)
    print(config.id2label)
except Exception as e:
    print(f"Error: {e}")
