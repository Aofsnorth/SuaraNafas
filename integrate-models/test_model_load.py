import torch

from model import load_model, predict_tb_risk


model = load_model()
risk = predict_tb_risk(
    model,
    torch.zeros(5, 1, 128, 36),
    torch.zeros(1, 43),
)

assert 0.0 <= risk <= 1.0
print(f"Model loaded successfully. Dummy TB risk: {risk:.4f}")
