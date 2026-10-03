# Audit model dan training lokal — 3 Oktober 2026

## Ringkasan

- Ada **6 checkpoint CODA terlatih**, bukan hanya rencana training. Lima cocok dengan SHA-256 manifest dan lolos strict load serta forward smoke test. `output-long-fixed` gagal pemeriksaan hash, meskipun tensor dapat dimuat.
- Checkpoint residual v2/TBscreen yang disebut README **tidak ditemukan di checkout ini**; AUROC 0,639 dari dokumentasi tidak diperlakukan sebagai pengukuran ulang.
- Dibuat dan benar-benar dilatih di **NVIDIA RTX 4060 Laptop GPU, 8 GB**: kandidat `frozen_ast_linear_v1`, encoder AST AudioSet resmi dibekukan + classifier logistic terregularisasi, dengan input audio dan 27 fitur klinis.
- Kandidat baru **tidak mengalahkan CNN v3**. Tidak ada dasar untuk klaim algoritma nomor satu dunia atau untuk promosi ke production.
- Semua gate deployment tetap `blocked`. Model baru hanya dapat dipakai lewat entry point riset terpisah, bukan `app.py` production.

## Model historis

Angka berikut berasal dari metrik tersimpan, bukan training ulang. Sensitivitas/spesifisitas historis memakai threshold 0,5. Run longitudinal dan non-longitudinal tidak memiliki cohort/input identik.

| Direktori | Arsitektur | AUROC tersimpan | Sensitivitas | Spesifisitas | Integritas |
|---|---|---:|---:|---:|---|
| `output-long` | v3 | 0,8005 | 77,2% | 70,7% | Hash/load/smoke lulus |
| `output-long-fixed` | v3 | 0,7825 | 71,9% | 67,9% | **Hash berbeda: jangan dipercaya sebagai artifact yang dideklarasikan** |
| `output-spec` | v3 | 0,7787 | 70,2% | 71,5% | Hash/load/smoke lulus |
| `output-v3` | v3 | 0,7780 | 69,3% | 72,2% | Hash/load/smoke lulus |
| `output-v3-long` | v3 | 0,7758 | 68,4% | 71,5% | Hash/load/smoke lulus |
| `output-v4` | v4 | 0,7638 | 64,9% | 71,2% | Hash/load/smoke lulus |

Pooled test historis menggabungkan repeated holdout: 416 observasi dari 380 pasien unik; `output-long` 418 dari 377. Tidak ada overlap train/validation/test dalam satu fold. Ini bukan otomatis label leakage untuk AUROC, tetapi observasi pooled bukan semuanya independen. AP historis juga perlu diinterpretasikan dengan batasan implementasi tie yang dijelaskan di bawah.

Bukti lengkap: `coda-tb/benchmark-ast-v1/historical-audit.json`.

## Temuan audit algoritma dan protokol

1. **Threshold fusion lama memakai pooled test labels.** `training/cross_validate_fusion.py` memilih threshold setelah mengumpulkan prediksi test. Evaluasi sensitivitas/spesifisitas pada threshold tersebut bukan holdout independen. AUROC tidak bergantung threshold, sehingga jangan menyatakan AUROC pasti bocor karena masalah ini saja.
2. **Resep refit final berbeda bila augmentation/distillation diaktifkan.** Opsi di CV tidak seluruhnya diteruskan ke refit final. Benchmark baru tidak memakai opsi tersebut dan tidak menggunakan bobot final lama sebagai evaluasi holdout.
3. **Average precision historis tidak mengelompokkan tied scores.** `training/metrics.py` dapat memberi AP berbeda untuk urutan label berbeda pada skor identik. Benchmark baru memakai implementasi scikit-learn.
4. **Padding melewati BatchNorm sebelum masking pada fusion CNN.** Ini dapat mengubah statistik training berdasarkan komposisi batch. Tidak diperbaiki dalam audit ini; tetap menjadi batasan pembanding v3/v4.
5. **Jalur teacher lama memiliki risiko alignment cache, sampling rate campuran, dan model ID tidak konsisten.** Kandidat baru memakai extractor terpisah dengan cache berbasis konten, resampling per rekaman, serta revision resmi yang dipin.
6. **Tidak ada kalibrasi probabilitas.** Model lama maupun baru tidak boleh mengklaim skor sebagai probabilitas TB populasi.
7. **Country dan jumlah rekaman bisa menjadi shortcut.** Metadata klinis memang meningkatkan diskriminasi, tetapi manfaat audio harus dibuktikan terhadap clinical-only; split pasien belum membuktikan generalisasi antarnegara/perangkat.
8. **Dokumentasi lama mengandung klaim terlalu kuat.** Tidak adanya kelas TB pada AudioSet tidak membuktikan tiadanya overlap sumber atau confounding; angka antarartikel/dataset bukan ranking langsung. Contoh PPV 85% sensitivitas, 85% spesifisitas, prevalensi 1% dalam roadmap juga salah: PPV yang benar sekitar **5,41%**, bukan 0,76%.

Tidak ada perbaikan diam-diam pada pipeline lama atau penggantian checkpoint milik pengguna. File baru mengisolasi protokol yang digunakan untuk eksperimen ini.

## Dataset yang benar-benar digunakan

- CODA solicited lokal: **1.039 pasien**, 283 TB / 756 non-TB, tujuh negara.
- **6.746 WAV terpilih**, maksimum delapan clip per pasien dengan kebijakan loader yang sama untuk semua pembanding.
- 65 peserta tidak memiliki audio lokal; satu tidak memiliki reference label. Loader melaporkan penghilangan ini.
- SHA-256 audio terpilih: 6.746 konten unik; tidak ditemukan duplikat byte lintas pasien pada subset terpilih. Ini tidak memeriksa near-duplicate atau seluruh arsip.
- Tidak menambahkan longitudinal/TBscreen T2; tidak mengunduh audio atau data pasien baru.
- Indonesia tidak termasuk cohort. Tidak ada klaim validasi untuk Indonesia.

## Protokol perbandingan baru

- Outer `StratifiedKFold`, 3 fold, seed 42; setiap pasien menghasilkan **satu** prediksi out-of-fold.
- Dalam masing-masing outer development partition, 20% dijadikan inner validation. Train/validation/test pasien saling disjoint. Tidak melakukan full inner nested CV.
- Clinical preprocessing dan scaler head hanya di-fit pada train fold.
- Epoch CNN dipilih dengan validation AUROC (budget 8 epoch). Head dilatih sampai 120 epoch; L2 `{0,001; 0,01; 0,1}` dan epoch dipilih dengan validation AUROC.
- Threshold dipilih dari **validation saja**: threshold finite tertinggi yang mencapai sensitivitas minimal 90%. Sensitivitas test tidak dijamin mencapai target.
- Tidak memakai label test untuk hyperparameter/threshold. AST+clinical ditetapkan sebagai kandidat sebelum melihat test results.
- Evaluasi pooled sensitivitas/spesifisitas memakai threshold terkunci masing-masing fold, bukan threshold baru dari pooled test.
- Interval AUROC memakai 2.000 paired stratified subject bootstrap, seed 2026, dalam strata fold × label. Interval bersifat **conditional pada prediksi OOF tetap**; tidak menangkap ketidakpastian retraining/model selection dan bukan validasi eksternal.
- Budget/tuning antar keluarga model berbeda, sehingga hasil menunjukkan performa resep yang dijalankan, **bukan potensi optimal seluruh algoritma**. CNN memakai frontend 1,5 detik sendiri; AST memakai frontend resmi sampai 10,24 detik. Perbandingan adalah pipeline pada pasien/clip identik, bukan isolasi arsitektur semata.

## Hasil training baru

| Model | AUROC pooled [95% CI] | Mean AUROC fold ± SD | AP | Sensitivitas | Spesifisitas |
|---|---|---|---:|---:|---:|
| CNN fusion v3 | **0,8104 [0,7801–0,8368]** | 0,8134 ± 0,0063 | 0,6326 | 92,2% | 38,6% |
| CNN fusion v4 | 0,8044 [0,7752–0,8296] | 0,8130 ± 0,0151 | 0,5785 | 92,2% | **45,4%** |
| Clinical-only | 0,7919 [0,7603–0,8191] | 0,8058 ± 0,0163 | 0,6123 | 91,2% | 43,5% |
| **AST + clinical (baru)** | 0,7607 [0,7276–0,7924] | 0,7634 ± 0,0367 | 0,5306 | 92,9% | 29,4% |
| AST audio-only | 0,6711 [0,6360–0,7056] | 0,6622 ± 0,0634 | 0,4144 | 89,0% | 25,4% |

| Model | TP | TN | FP | FN |
|---|---:|---:|---:|---:|
| CNN v3 | 261 | 292 | 464 | 22 |
| CNN v4 | 261 | 343 | 413 | 22 |
| Clinical-only | 258 | 329 | 427 | 25 |
| AST + clinical | 263 | 222 | 534 | 20 |
| AST audio-only | 252 | 192 | 564 | 31 |

Paired pooled delta AST+clinical − v3: **−0,0497 [−0,0736; −0,0248]**. Clinical-only − v3: −0,0185 [−0,0335; −0,0034]. Hindari klaim causal tentang kontribusi audio: v3 bukan ablation identik dari classifier clinical-only.

**Kesimpulan:** v3 terbaik pada AUROC pooled dalam eksperimen ini; v4 memiliki spesifisitas lebih tinggi pada operating point validation yang dipilih. Kandidat pretrained baru gagal menunjukkan peningkatan. Jangan mengubah model berdasarkan test ini lalu melaporkan test yang sama sebagai konfirmasi independen.

## Artifact baru dan inference

Artifact: `coda-tb/benchmark-ast-v1/candidate/head.pt` + `manifest.json`, dan encoder di `ast_model/f826b80d28226b62986cc218e5cec390b1096902/`.

- Encoder resmi `MIT/ast-finetuned-audioset-10-10-0.4593`, revision dipin, hanya safetensors/config diunduh, tanpa remote Python code. Sumber/lisensi BSD-3-Clause diverifikasi; provenance bukan sertifikasi keamanan mutlak.
- Head 795 input (768 AST + 27 klinis), **796 parameter trainable**. Encoder sekitar 86 juta parameter frozen; jangan membandingkan ukuran head saja dengan seluruh CNN.
- Refit seluruh development cohort: **35 epoch, L2 0,1, seed 42**, dipilih sebagai median seleksi validation fold; bukan tuning ulang pada test.
- Evaluasi manifest adalah **bukti resep CV**, bukan evaluasi final refit pada data eksternal.
- Median threshold disimpan sebagai provisional, tidak dipakai CLI untuk diagnosis/risk bands.
- CPU dan GPU inference pada enam WAV nyata berhasil. Same-device/batch cached-feature parity error 0,0 pada smoke sample. Selisih CPU/GPU yang diukur 0,0000607; jangan mengklaim bitwise cross-device parity.
- Smoke sample berasal dari development cohort: membuktikan eksekusi/paritas, bukan akurasi baru. Cold inference terukur sekitar 18,85 detik GPU / 19,42 detik CPU untuk enam clip termasuk load/hash; bukan benchmark latency representatif.
- Tidak terhubung otomatis ke FastAPI/Next.js. CLI menerima **metadata raw CODA**, bukan JSON form web. Snapshot dan head harus dipindahkan bersama bila diekspor.

## Reproduksi (PowerShell, dari `deploy/model-space`)

Environment terisolasi: `../../.venv-gpu/Scripts/python.exe`; versi lengkap di `coda-tb/benchmark-ast-v1/environment.txt`.

```powershell
$env:CUDA_LAUNCH_BLOCKING = "1"
../../.venv-gpu/Scripts/python.exe -u -m training.run_benchmark `
  --clinical-metadata ../../coda-tb/meta/clinical.csv `
  --additional-metadata ../../coda-tb/meta/additional.csv `
  --solicited-metadata ../../coda-tb/meta/solicited.csv `
  --audio-root ../../coda-tb/_raw/dataset/raw_data/solicited_data `
  --output-dir ../../coda-tb/benchmark-ast-v1-reproduction `
  --device cuda --ast-batch-size 1 --folds 3 --cnn-epochs 8 --head-epochs 120
```

Output baru sengaja diperlukan agar laporan/checkpoint run selesai tidak ditimpa. Runner melakukan benchmark; fungsi `export_candidate` membuat refit kandidat dari laporan validation yang selesai. Perintah inference riset:

```powershell
../../.venv-gpu/Scripts/python.exe -m training.ast_candidate `
  --candidate-dir ../../coda-tb/benchmark-ast-v1/candidate `
  --audio <path-WAV-nyata> `
  --metadata <path-JSON-raw-CODA-lengkap> --device cpu
```

Ganti path contoh dengan file sendiri. JSON metadata wajib memuat `sex`, `Country`, `HIVstatus`, seluruh `NUMERIC_FIELDS` dan `BINARY_FIELDS` dari `training/encoding.py`. `tb_prior="Not sure"` dipertahankan seperti training; field binary lain hanya Yes/No. Jangan menaruh data pasien dalam Git.

Log aktual: `extraction-batch1.log`, `training.log`, `refit-complete.log`, `inference-smoke-complete.log`. Laporan: `cnn-reports.json`, `head-reports.json`, `summary.json`, `historical-audit.json`, `inference-smoke.json`.

## GPU dan keterbatasan operasional

PyTorch default adalah CPU-only. Dibuat `.venv-gpu` dengan `torch==2.11.0+cu128` dari index resmi PyTorch; CUDA matrix smoke berhasil. Run AST batch 4 mengalami illegal memory access setelah 48 pasien; proses baru dengan batch 1 dan `CUDA_LAUNCH_BLOCKING=1` berhasil menyelesaikan cohort. **Akar error driver/kernel belum dibuktikan**. Tidak mengubah driver atau mengklaim bug CUDA diperbaiki. Snapshot/hasil cache valid dipertahankan. Runtime kandidat memakai batch 1; rekomendasikan flag sinkron yang sama bila memakai GPU lokal ini.

Perbaikan metadata export menambahkan kategori CODA `tb_prior="Not sure"` agar parity training/inference terjaga, bukan mengubah label.

## Validasi dan langkah riset berikutnya

Suite backend dijalankan menggunakan environment GPU; hasil final dicatat pada akhir pekerjaan. Tidak ada perubahan frontend, sehingga build frontend tidak dijalankan.

Tahap berikutnya bukan menjanjikan model nomor satu: gunakan cohort eksternal yang benar-benar tidak disentuh, cek generalisasi negara/perangkat dan manfaat audio, lakukan kalibrasi dari data pengembangan independen, serta evaluasi kandidat lain (misalnya PaSST/MFCC/late fusion) sebagai eksperimen baru dengan protocol terkunci. Perbandingan publikasi CODA menunjukkan clinical+cough lebih kuat daripada cough-only, tetapi angka artikel bukan target yang dijamin tercapai pada subset lokal ini.

Sumber diperiksa: [hasil CODA challenge](https://www.medrxiv.org/content/10.1101/2024.05.13.24306584v1), [dataset CODA](https://pmc.ncbi.nlm.nih.gov/articles/PMC10996751/), [model AST resmi](https://huggingface.co/MIT/ast-finetuned-audioset-10-10-0.4593). Laporan preprint/benchmark tidak setara validasi klinis deployment Indonesia.
