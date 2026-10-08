"""Download model weights ahead of time (so the first job does not wait, and the server can run offline)."""
import os
import sys

name = os.environ.get("NOTNEGAR_DEMUCS_MODEL", "htdemucs_6s")
try:
    from demucs.pretrained import get_model
    get_model(name)
    print("demucs model ready:", name)
except Exception as e:
    print("demucs model not downloaded:", e)
    sys.exit(1)
try:
    import torch
    import torchcrepe
    torchcrepe.predict(torch.zeros(1, 16000), 16000, 160, 50, 1000, model="full", batch_size=64, device="cpu")
    print("crepe model ready")
except Exception as e:
    print("crepe not ready:", e)
