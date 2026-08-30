# SuaraNafas research screening backend

FastAPI backend dan pipeline CNN audio untuk prototipe **skrining riset**, bukan
diagnosis TB. Production sengaja berada dalam status `degraded` sampai tersedia
artefak yang benar-benar lolos validasi eksternal.

## Status saat ini

Kandidat terbaru adalah `residual_spectrogram_cnn_v2`:

- arsitektur residual lokal di `src/model.py`;
- 307.762 parameter trainable;
- inisialisasi acak PyTorch;
- tidak mengimpor ResNet, VGGish, model zoo, atau bobot pretrained;
- optimizer mencakup seluruh parameter model;
- checkpoint, konfigurasi preprocessing, fold hash, dan metrik dicatat di
  manifest;
- `evaluation_gate.status` tetap `blocked`;
- `external_validation` tetap `false`.

Istilah *from scratch* hanya berarti bobot neural network dimulai secara acak
tanpa transfer learning. PyTorch dan NumPy tetap digunakan sebagai library
komputasi. From-scratch tidak otomatis berarti akurat atau aman secara medis.

## Input dan output model

Input model adalah satu atau lebih PCM WAV. Pipeline mengubah setiap jendela
batuk menjadi tensor log-mel berukuran `(1, 64, 101)`:

- sample rate 44,1 kHz;
- jendela 1 detik dengan energi tertinggi;
- periodic Hann 1.102 sampel;
- hop 441 sampel;
- FFT 2.048;
- 64 mel bins, HTK scale, Slaney normalization;
- centered STFT dengan reflect padding;
- power-to-dB dengan rentang 80 dB;
- min-max normalization per klip.

Arsitektur menghasilkan dua logits per klip. Probabilitas tiap klip dirata-rata
menjadi satu skor pasien. Output API adalah skor rujukan kontinu dan risk band,
bukan pernyataan positif/negatif TB.

## Dataset

Training lokal menggunakan raw WAV **passive cough** TBscreen:

- sumber: [Zenodo 10431329](https://doi.org/10.5281/zenodo.10431329);
- lisensi: CC-BY 4.0;
- lokasi studi: Nairobi, Kenya;
- label referensi: TB vs non-TB;
- hanya audio dengan `Permission_sound == "Yes"`;
- forced cough tidak dicampur karena protokol dan domain rekamannya berbeda.

Subset terunduh berisi 123 subjek dan 2.321 klip. Dua subjek quarantine yang
pernah dilihat manual selalu dikeluarkan. Evaluasi nested terbaru memakai 70
subjek consented yang juga masuk fold T1 resmi: 37 TB dan 33 non-TB, total 1.319
klip. Dataset mempunyai risiko confounding cohort-label dan hanya berasal dari
satu lokasi studi.

Jangan commit audio, metadata pasien, atau generated training output. Direktori
`data/` dan `training-output*/` diabaikan Git.

## Unduh subset TBscreen

Dari `deploy/model-space`:

```bash
python -m pip install -r requirements-dev.txt
python download_tb_screen.py
```

Downloader idempotent dan dapat melanjutkan file yang belum ada. Arsip lengkap
sangat besar; downloader hanya mengambil subset yang dibutuhkan.

## Training residual dari nol

Single holdout run untuk eksperimen cepat:

```bash
python -m training.train \
  --passive-metadata data/tbscreen/TBscreen_Dataset/Passive_coughs/Passive_coughs.csv \
  --audio-root data/tbscreen/TBscreen_Dataset/Passive_coughs/Audio_files \
  --output-dir training-output-residual-holdout \
  --epochs 25 \
  --batch-size 8 \
  --seed 42 \
  --device auto \
  --no-augmentation
```

Single holdout tidak cukup untuk quality gate. Evaluasi utama memakai nested
patient-level CV dengan fold T1 resmi:

```bash
python -m training.cross_validate \
  --passive-metadata data/tbscreen/TBscreen_Dataset/Passive_coughs/Passive_coughs.csv \
  --audio-root data/tbscreen/TBscreen_Dataset/Passive_coughs/Audio_files \
  --fold-directory data/tbscreen/reference/folds \
  --output-dir training-output-residual \
  --epochs 25 \
  --batch-size 8 \
  --seed 42 \
  --device cuda \
  --no-augmentation
```

Untuk reproduksi evaluasi, tambahkan satu `--exclude-subject` untuk setiap ID
dalam daftar quarantine lokal. Daftar tersebut sengaja tidak disimpan di Git.

Untuk setiap outer fold, empat inner fits membuat out-of-fold validation
predictions. Epoch dan threshold dipilih hanya dari inner validation. Model lalu
dilatih ulang pada seluruh outer-training subjects dan outer test fold dievaluasi
satu kali. Setelah lima outer folds, final research checkpoint dilatih pada semua
70 subjek menggunakan median epoch pilihan inner CV.

## Hasil nested internal

| Metrik | Hasil |
|---|---:|
| Subjek OOF | 70 (37 TB / 33 non-TB) |
| Pooled AUROC | 0,639 |
| Average precision | 0,611 |
| Brier score | 0,241 |
| Outer-fold AUROC | 0,603; 0,794; 0,857; 0,500; 0,548 |

Operating point sensitif dipilih secara terpisah pada inner validation untuk
masing-masing outer fold:

| Hasil | Jumlah |
|---|---:|
| True positive | 31 |
| False negative | 6 |
| True negative | 9 |
| False positive | 24 |
| Sensitivity | 83,8% |
| Specificity | 27,3% |

Hasil ini **tidak memenuhi quality gate**: masih ada enam false negative dan
false positive sangat tinggi. Variasi antar-fold juga besar. Jangan menyesuaikan
hyperparameter lalu mengklaim fold yang sama sebagai test baru.

Generated research artifact lokal:

```text
training-output-residual/model-audio-residual.pt
training-output-residual/manifest-audio-residual.json
training-output-residual/metrics-audio-residual.json
```

Ketiganya tetap local-only dan blocked.

## Validasi eksternal yang masih dibutuhkan

Dataset berikutnya adalah CODA TB DREAM di
[Synapse](https://www.synapse.org/TBcough) (`10.7303/syn31472953`). Akses
memerlukan akun Synapse milik operator, validasi/certification, Intended Data Use,
dan penerimaan syarat dataset. Kredensial dan persetujuan tidak boleh dibypass
atau dimasukkan ke repository.

Setelah akses disetujui, gunakan environment download terpisah dan jalankan
`download_coda.py` dengan `SYNAPSE_AUTH_TOKEN`. Kandidat hanya boleh dipertimbangkan
untuk production setelah evaluasi patient-level pada data eksternal/held-out,
confidence interval, dan target sensitivity/specificity yang ditetapkan sebelum
evaluasi semuanya lulus.

## Jalankan backend lokal

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
uvicorn app:app --host 127.0.0.1 --port 7860 --reload
```

Tanpa model tervalidasi, `GET /health` harus melaporkan:

```json
{
  "status": "degraded",
  "model_status": "unavailable",
  "prediction_enabled": false
}
```

### Uji kandidat hanya di staging/local

```bash
DEPLOYMENT_ENV=staging \
MODEL_MANIFEST_PATH=training-output-residual/manifest-audio-residual.json \
ALLOW_BLOCKED_CANDIDATE=true \
uvicorn app:app --host 127.0.0.1 --port 7860
```

Health tetap melaporkan `model_status: candidate`. Konfigurasi ini hanya untuk
menguji integrasi aplikasi, bukan screening publik. `DEPLOYMENT_ENV=production`
selalu menolak kandidat, walaupun `ALLOW_BLOCKED_CANDIDATE=true` ikut terpasang.

## Hubungkan ke Next.js

Tambahkan ke `.env.local` pada root project:

```env
BACKEND_API_URL=http://127.0.0.1:7860
ALLOW_DEMO_MODE=false
```

Endpoint `POST /predict` menerima `multipart/form-data` dengan `metadata` JSON
dan satu sampai delapan PCM WAV pada field `audio`. Sampel/model berasal dari
cohort Kenya, bukan Indonesia. Skor tidak dapat memastikan atau menyingkirkan TB
dan tidak boleh menunda tes dahak, tes molekuler, rontgen, atau konsultasi medis.
