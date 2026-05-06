from transformers import AutoConfig, AutoFeatureExtractor
import sys

model_id = "UMUTeam/w2v-bert-emotion-es"
try:
    config = AutoConfig.from_pretrained(model_id)
    print(f"Labels: {config.id2label}")
    print(f"Model Type: {config.model_type}")
    
    # Check if feature extractor is compatible
    feature_extractor = AutoFeatureExtractor.from_pretrained(model_id)
    print(f"Feature Extractor: {type(feature_extractor)}")
except Exception as e:
    print(f"Error: {e}")
