# Peta Jalan Riset: Menuju Skrining Batuk TB yang Hebat

Status dokumen: rencana kerja, bukan laporan hasil.
Terakhir diperbarui: 2026.

Dokumen ini menjelaskan *mengapa* setiap keputusan diambil dan *bukti apa* yang
mendasarinya, sehingga keputusan berikutnya bisa ditinjau kritis alih-alih
diulang dari keyakinan.

---

## 1. Ringkasan posisi saat ini

| Aspek | Nilai | Sumber |
| --- | --- | --- |
| Arsitektur aktif | `residual_spectrogram_cnn_v2`, 307.762 parameter | `src/model.py` |
| Inisialisasi | `random_pytorch_default`, tanpa bobot pretrained | `training/cross_validate.py` |
| Data latih | TBscreen T1, 70 subjek (37 TB / 33 non-TB) | `download_tb_screen.py` |
| `input_mode` | `audio` — 16 variabel klinis dibuang | `src/model.py` (`del metadata`) |
| AUROC (pooled) | **0,639** | `evaluation` pada manifest |
| Sensitivitas / spesifisitas | 83,8% / 27,3% | manifest |
| `evaluation_gate.status` | `blocked` | `training/artifact_manifest.py` |

Tiga hal di atas harus dibaca bersamaan: angka 0,639 **bukan** kegagalan
implementasi, melainkan konsekuensi langsung dari tiga keputusan yang saling
mengunci. Tidak ada satu pun yang bisa diperbaiki hanya dengan menyetel
hyperparameter.

---

## 2. Empat peng Diagnosis yang Mengunci Kinerja

### 2.1 `input_mode="audio"` membuang seluruh data klinis

Alur saat ini: formulir web mengirim 16 variabel klinis → tervalidasi dua kali
(frontend dan backend) → diteruskan ke model → **lalu dihapus** oleh
`ResidualSpectrogramClassifier.forward`.

Bukti bahwa fusion menaikkan kinerja, dari dua studi independen:

- Studi Zambia (arXiv 2509.09746, 500 peserta): Wav2Vec2 yang disetel halus hanya
  dengan audio AUROC **0,852**; ditambah demografi + klinis menjadi **0,921** pada ambang
  0,38 (sens 90,3% / spec 73,1%, memenuhi TPP WHO).
- DeepGB-TB (arXiv 2508.02741, 1.105 pasien, 7 negara): audio-saja 0,825;
  tabular-saja 0,840; **gabungan 0,903**. Pada kohort ini, klinis saja mengalah
  audio saja.

Embeddings audio dari model berukuran besar umumnya tidak se-efficient 27
angka klinis berskala kecil yang dikumpulkan formulir.

### 2.2 N=70 adalah plafon, bukan titik awal

Artikel asli (Sharma et al., *Science Advances* 2024) melaporkan baseline
ResNet18-ImageNet di **0,79 ± 0,06** pada T1 dan **0,82 ± 0,03** pada T2.
Artinya datanya sendiri mendukung AUROC 0,79–0,82. Yang hilang adalah
kemampuan model, bukan datanya.

Yang tersedia tapi belum dipakai:

| Set | Subjek | TB / non-TB | Rekaman | Peran menurut artikel | Status di sini |
| --- | --- | --- | --- | --- | --- |
| TBscreen T1 | 90 | 45 / 45 | ±21.133 | latih + validasi 5-fold | Dipakai 70 subjek |
| TBscreen T2 | 149 | 103 / 46 | 33.641 | **test set** (superset T1) | Belum dipakai |
| CODA TB DREAM | 1.105 (split latih) | — | 9.772 di `syn40358494` | latih lintas negara | Folder terverifikasi, metadata perlu token |

**Jangan menyerap T2 ke data latih.** Artikel asli secara eksplisit memakai T2
sebagai test set: model dilatih pada fold 2–5 T1, lalu diuji pada fold 1 T2.
Menyerap T2 ke latih akan menghapus justru embargo yang membuat angka artikel
bisa dipercaya. Cara menambah subjek yang benar adalah menambah *sumber*
(CODA TB), bukan menambah himpunan holdout.

### 2.3 Larangan "from scratch" adalah penyebab utama, bukan kebanggaan

Codebase ini sudah benar-benar from-scratch di 4 titik (lihat
`docs/DATASET_PROTOCOL.md` §From-scratch). Masalahnya bukan kejujuran
terminologinya, melainkan hasil konkretnya:

- CODA benchmark (arXiv 2606.17337), split subject-disjoint:
  PaSST **0,7228** > x-vector 0,7182 > MFCC 0,7036 > WavLM 0,6914 >
  Whisper 0,6457.
- Tesis Stellenbosch: *pre-training "almost always improved performance, and
  always led to better generalisation, observed by a reduction in metric
  standard deviation across evaluation sets."*

Kalimat kedua itu menjawab pertanyaan yang tidak pernah ditanyakan: kenapa
AUROC per-fold kita melompat **0,500 → 0,603 → 0,794 → 0,857**? Preseeding
memberi CNBC stabilitas lintas fold, bukan hanya nilai rata-rata.

### 2.4 "90% accuracy" adalah target yang menyesatkan

Dengan prevalensi TB populasi nyata (±1%), model yang **selalu menjawab "tidak
TB"** sudah mencapai akurasi ~99%. Jadi accuracy tidak mengukur apa pun yang
berguna untuk skrining. Yang relevan adalah PPV dan NPV.

Sebagai gantinya, berikut target yang kami pakai, dalam bahasa non-teknis:

| Metrik | Nilai sekarang | Target | Mengapa |
| --- | --- | --- | --- |
| Sensitivitas | 83,8% | ≥ 85% | jangan lewatkan pasien |
| **Spesifisitas** | **27,3%** | **≥ 85%** | 1 dari 4 orang sehat dirujuk lebih lanjut |
| AUROC | 0,639 | ≥ 0,85 | urutan risiko, dipakai untuk memilih ambang |
| Akurasi | 57% | — | **tidak dipakai sebagai target** |

Spesifisitas adalah angka yang paling perlu diperbaiki dan paling sering
diabaikan. Pada kohort dengan 33 non-TB, spesifisitas 27,3% berarti 24 orang
perlu rujukan palsu.

---

## 3. Fase Kerja

### Fase 1 — Fusion + perbaikan cakupan ✅ (selesai)

| Perubahan | File | Alasan |
| --- | --- | --- |
| Arsitektur `residual_fusion_cnn_v3` (312.820 param, fusion 27-dim) | `src/model.py` | V2 tidak diubah agar bisa warm-start & versioned |
| `ClinicalPreprocessor` dipakai &_country diperbaiki | `training/encoding.py` | `SA` (Arab Saudi) → `ZA` (Afrika Selatan) |
| Runner cross-validation fusion | `training/cross_validate_fusion.py` | Runner sebelumnya hanya audio-saja |
| `KE` masuk daftar sah | `src/metadata.py` | Manifest mendeklarasikan `["KE"]` tetapi gate menolaknya: deadlock |
| `COUNTRY_NOT_VALIDATED` terpisah dari `OUT_OF_DISTRIBUTION` | `app.py`, `route.ts` | Indonesia perlu jawaban jujur, bukan "wilayah tak dikenal" |
| `code` diteruskan ke klien | `src/app/api/analyze/route.ts` | Kode error sebelumnya dibuang, semua kegagalan jadi satu pesan |

Ukuran artifact tetap ±1,2 MB karena fusion menambah MLP kecil, bukan backbone.

### Fase 2 — Guru pretrained via distillation (kode siap, belum dijalankan)

**Keputusan: pakai guru beku, bukan Adsitpsi pretrained.** Guru hanya
membentuk gradien selama pelatihan lalu dibuang, sehingga
`pretrained_weights` tetap `False` dan ukuran artifact tidak berubah.

- Guru: `facebook/ast-finetuned-audioset-10-10-0.97` (AST).
- Alasan memilih AST, bukan PaSST/Wav2Vec2/Whisper: *batuk bukan suara manusia yang articulatif*;
  pada CODA, Whisper (0,6457) performs lebih buruk dari MFCC (0,7036).
  AudioSet tidak punya kelas TB, jadi encoding tidak bisa membocorkan label.
- AST dipilih **implementasi**: Ia sudah ada di `transformers` dengan front end
  numpy, jadi `torchaudio` tidak perlu dipasang.
- Catatan: *batuk bukan suara manusia yang articulatif*. Pada CODA, Whisper
  (0,6457) berkinerja lebih buruk daripada MFCC (0,7036), jadi model bahasa
  tidak otomatis menjadi pilihan yang tepat. AudioSet tidak punya kelas TB,
  sehingga encoding tidak bisa membocorkan label.
- Loss: KL divergens bersuhu dengan detach defensif pada guru.
- Cache embedding: kunci SHA-256 dari bytes audio **dan** id guru, supaya
  entri basi dari guru berbeda tidak ikut terpakai.

Rasio ini sudah diverifikasi secara numerik: `distillation_loss` bernilai tepat
`0.0` ketika student identik dengan guru, dan cocok dengan `F.kl_div`.

### Fase 3 — CODA TB (blocked oleh persetujuan Synapse)

Tidak bisa diselesaikan oleh kode saja. Butuh: akun Synapse, status
*Certified & Validated*, dan pernyataan penggunaan ≤500 kata. Rinciannya di
`docs/DATASET_PROTOCOL.md`.

Harapan: 1.105 peserta × 7 negara, lisensi **CC-BY 4.0** (komersial diizinkan).
Literatur lapangan: spesifisitas di dunia nyata **tidak pernah** melewati
73–83%, sehingga kombinasi "spesifisitas 90% + akurasi 90%" tidak ada di
jurnal.

---

## 4. Metrik yang Jujur

Hari ini sengaja pakai **prevalensi kohort**, bukan prevalensi populasi:

```
PPV = 0.49–0.53   NPV = 0.87–0.90
```
(MDPI *Sensors* 2026, 26(4):1223, subset CODA)

Angka itu sudah memperhitungkan base-rate. Hal yang perlu dipikirkan ulang
setiap kali angka sasaran diubah:

> Pada prevalensi 1%, dengan sensitivitas 85% dan spesifisitas 85%,
> PPV hanya **0,76%**. Artinya dari 1.000 orang yang diskrining, sekitar 7 kasus
> benar dan 128 dirujuk keliru.

Ini alasan utama produk ini tidak bolehEssential divisão pretensi sebagai alat
diagnosis, terlepas dari nilai AUROC.

Literatur juga memberi peringatan: angka tinggi terdahulu (Pahar 0,94 pada 51
peserta; ResNet50 0,92) memakai split yang tidak memisahkan antar-peng coughing,
sehingga gelembung. Split subject-disjoint bukan pilihan, tapi syarat.

---

## 5. Apa yang Tidak Akan Kami Kerjakan

Menuliskan ini agar ekspektasi tetap realistis:

1. **Melewati `evaluation_gate`.** Gate `blocked` adalah aset terbaik proyek
   ini. Tidak akan dilonggarkan untuk mengejar angka.
2. **Melaporkan AUROC dari split yang tidak subject-disjoint.** Inflasi adalah
   cara tercepat merusakkan kredibilitas.
3. **Mengklaim validasi untuk Indonesia.** Tidak ada dataset TB Indonesia yang
   bisa diakses; jalan yang jujur adalah mengatakannya terus terang.
4. **Optimasi spesifisitas tanpa menyebut orientasi klinisnya.** Prevalensi
   skrining komunitas mendorong sensitivitas, bukan spesifisitas. Kalau fokus
   FP tetap dipertahankan, UI harus diberi label "alat sortir, bukan alat
   diagnosis" — bukan hanya di halaman transparency.
