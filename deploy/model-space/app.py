import os

from fastapi import FastAPI, File, HTTPException, UploadFile

app = FastAPI(title="Deteksi TB - Model API")

# TODO: load your trained CNN once at startup, for example:
# import tensorflow as tf
# MODEL = tf.keras.models.load_model(os.path.join(os.path.dirname(__file__), "model.h5"))

RISK_MESSAGE = {
    "low": "Model tidak menemukan pola menonjol pada sampel ini.",
    "medium": "Terdapat pola yang perlu ditinjau lebih lanjut.",
    "high": "Model menandai pola berisiko tinggi. Perlu konfirmasi klinis.",
}

RISK_RECOMMENDATION = {
    "low": "Pantau gejala; konsultasikan ke tenaga medis bila berlanjut.",
    "medium": "Disarankan pemeriksaan lanjutan di fasilitas kesehatan.",
    "high": "Segera lakukan pemeriksaan konfirmasi (dahak/rontgen) di fasilitas kesehatan.",
}


@app.get("/")
def health():
    return {"status": "ok", "service": "deteksi-tb-model-api"}


@app.post("/predict")
async def predict(audio: UploadFile = File(...)):
    data = await audio.read()
    if not data:
        raise HTTPException(status_code=400, detail="File audio kosong.")

    # === TODO: replace with real inference ===
    # 1) decode audio (e.g. librosa) -> mel-spectrogram
    # 2) probs = MODEL.predict(spectrogram) -> per-class probabilities
    # The block below is a deterministic placeholder so the endpoint is testable
    # end-to-end before the real model is attached.
    score = (len(data) % 100) / 100.0
    risk = "high" if score >= 0.66 else "medium" if score >= 0.33 else "low"
    confidence = round(0.6 + score * 0.39, 2)
    # =========================================

    return {
        "risk": risk,
        "confidence": confidence,
        "message": RISK_MESSAGE[risk],
        "recommendation": RISK_RECOMMENDATION[risk],
        "detail": {
            "scores": [
                {"label": "TB", "value": round(score, 2)},
                {"label": "Non-TB", "value": round(1 - score, 2)},
            ],
            "features": [
                {"label": "Ukuran sampel", "value": f"{len(data)} bytes"},
                {"label": "Tipe berkas", "value": audio.content_type or "unknown"},
            ],
            "model": {"name": "cnn-tb", "version": "0.1.0", "durationMs": 0},
        },
    }
