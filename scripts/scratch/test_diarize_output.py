import torch
import os
from pyannote.audio import Pipeline
from dotenv import load_dotenv

load_dotenv()

def test_pipeline():
    token = os.getenv("HF_TOKEN")
    if not token:
        print("HF_TOKEN not found")
        return

    pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", token=token)
    
    # Create a dummy waveform (1 second of silence)
    sample_rate = 16000
    waveform = torch.zeros((1, sample_rate * 1))
    
    print("Running pipeline...")
    output = pipeline({"waveform": waveform, "sample_rate": sample_rate})
    
    print(f"Output type: {type(output)}")
    print(f"Attributes: {dir(output)}")

if __name__ == "__main__":
    test_pipeline()
