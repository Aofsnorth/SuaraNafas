# SuaraNafas research screening backend

FastAPI backend dan pipeline CNN audio untuk prototipe **skrining riset**, bukan
diagnosis TB. Backend sengaja berada dalam status `degraded` sampai ada model
yang sudah melalui validasi eksternal dan manifest-nya secara eksplisit
melewati evaluation gate.

## Provenance model

Model kandidat saat ini benar-benar dilatih dari inisialisasi acak:

- arsitektur lokal `spectrogram_audio_cnn_v1` di `src/model.py`;
- 26.498 parameter, semuanya trainable;
- tidak mengimpor ResNet, VGGish, model zoo, atau checkpoint pretrained;
- tidak memanggil `torch.load` sebelum optimisasi;
- `torch.load(..., weights_only=True)` hanya digunakan oleh runtime/XAI untuk
  membuka checkpoint hasil training proyek ini;
- manifest mencatat `initialization: random_pytorch_default` dan
  `pretrained_weights: false`.

Istilah *from scratch* berarti bobot neural network dimulai secara acak tanpa
transfer learning. PyTorch dan NumPy tetap dipakai sebagai framework komputasi.

## Dataset

Training menggunakan raw WAV **passive cough** dari TBscreen:

- sumber: [Zenodo 10431329](https://doi.org/10.5281/zenodo.10431329);
- lisensi: CC-BY 4.0;
- lokasi studi: Nairobi, Kenya;
- label: TB vs non-TB;
- hanya audio dengan `Permission_sound == "Yes"` yang dipakai;
- forced cough tidak dicampur agar protokol rekaman tidak menjadi shortcut.

Arsip lengkap berukuran sekitar 395 GB. Downloader menggunakan HTTP range
requests dan hanya mengambil maksimal 20 passive cough per subjek serta forced
cough yang tersedia. Run kandidat audio-only memakai 123 subjek dan 962 klip;
21 subjek berizin lain tidak mempunyai WAV yang cocok pada subset raw audio
yang dapat diunduh dari arsip publik.

Jangan commit audio, metadata pasien, atau hasil training. Direktori `data/`
dan `training-output/` sudah diabaikan oleh Git.

### Unduh subset

Dari `deploy/model-space`:

```bash
python -m pip install -r requirements-dev.txt
python download_tb_screen.py
```

Downloader bersifat idempotent dan melanjutkan file yang belum ada. Dependency
`remotezip==0.12.5` bersumber dari PyPI/GitHub resmi, berlisensi MIT, dan saat
diaudit tidak mempunyai advisory yang tercatat di metadata PyPI.

## Training dari nol

```bash
python -m training.train \
  --passive-metadata data/tbscreen/TBscreen_Dataset/Passive_coughs/Passive_coughs.csv \
  --audio-root data/tbscreen/TBscreen_Dataset \
  --output-dir training-output \
  --epochs 20 \
  --batch-size 8 \
  --seed 42
```

Pipeline:

- mengubah raw PCM WAV menjadi log-mel spectrogram lokal;
- menjaga seluruh klip pasien pada satu split;
- melakukan stratified patient-level train/validation/test split;
- menggunakan class-weighted cross entropy;
- memilih checkpoint berdasarkan AUROC validation terbaik;
- mengevaluasi test split satu kali setelah pemilihan checkpoint;
- menyimpan checkpoint, SHA-256, metrik, split summary, history, dan provenance.

### Hasil kandidat 20 epoch

| Split | Subjek | TB / non-TB | AUROC | Average precision | Brier |
|---|---:|---:|---:|---:|---:|
| Validation | 24 | 17 / 7 | 0,798 | 0,917 | 0,222 |
| Test internal | 24 | 17 / 7 | 0,538 | 0,773 | 0,222 |

Checkpoint terbaik berasal dari epoch 10. Performa test internal yang mendekati
acak menunjukkan model ini **belum layak untuk screening nyata**. Karena itu
`manifest-audio.json` tetap berisi:

```json
{
  "evaluation_gate": {
    "status": "blocked",
    "external_validation": false
  }
}
```

Jangan mengubah gate menjadi `passed` tanpa validasi eksternal yang terdokumentasi.

## XAI dari checkpoint baru

```bash
python -m training.generate_xai \
  --checkpoint training-output/model-audio.pt \
  --audio data/tbscreen/TBscreen_Dataset/Passive_coughs/Audio_files/PID_108A0_yeti.wav \
  --output ../../public/images/xai-from-scratch.png
```

Visualisasi menggunakan occlusion sensitivity pada model from-scratch tersebut,
bukan Grad-CAM dari model pretrained lama.

## Jalankan backend lokal

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
uvicorn app:app --host 127.0.0.1 --port 7860 --reload
```

Cek health:

```bash
curl http://127.0.0.1:7860/health
```

Tanpa model yang melewati gate, respons normal adalah:

```json
{
  "status": "degraded",
  "model_status": "unavailable",
  "prediction_enabled": false
}
```

Ini merupakan guard agar model acak, kandidat internal, atau checkpoint tanpa
validasi eksternal tidak pernah memberi skor medis.

### Uji checkpoint kandidat secara lokal

Checkpoint internal dapat diaktifkan hanya dengan opt-in eksplisit untuk menguji
alur aplikasi:

```bash
MODEL_MANIFEST_PATH=training-output/manifest-audio.json \
ALLOW_BLOCKED_CANDIDATE=true \
uvicorn app:app --host 127.0.0.1 --port 7860
```

Health endpoint harus tetap melaporkan `status: degraded` dan
`model_status: candidate`. Jangan gunakan konfigurasi ini untuk deployment
publik atau keputusan medis. Sampel dan cohort model berasal dari Kenya; pilih
negara `Kenya (cohort model kandidat)` ketika menguji form website.

## Hubungkan ke Next.js

Tambahkan di `.env.local` pada root project:

```env
BACKEND_API_URL=http://127.0.0.1:7860
```

Restart `npm run dev` setelah mengubah env. Model dilatih dari cohort Kenya
(`KE`), bukan Indonesia. Backend tetap harus menolak penggunaan di luar
distribusi validasi sampai tersedia data dan validasi eksternal Indonesia.

## Kontrak API

`POST /predict` menerima `multipart/form-data`:

- `metadata`: JSON string sesuai payload route Next.js;
- `audio`: satu sampai delapan PCM WAV dengan nama field yang sama berulang.

Respons mencakup probabilitas risiko TB, risk band, jumlah klip diterima,
status kualitas, uncertainty, identitas model, dan disclaimer. Hasil tidak boleh
dipakai untuk menyatakan seseorang positif/negatif TB atau menunda pemeriksaan
klinis.
