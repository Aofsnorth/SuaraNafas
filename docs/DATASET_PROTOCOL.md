# Protokol Data

Dokumen ini adalah kontrak antara data yang diunduh, kode yang dilatih, dan
angka yang dilaporkan. Tujuannya: siapa pun harus bisa mengaudit dari mana
setiap angka berasal, dan mengapa Indonesia secara sengaja tidak termasuk.

---

## 1. Sumber Data

### 1.1 TBscreen (latihan awal, Kenya)

- **DOI / arsip**: Zenodo 10431329 · artikel *Science Advances* 2024, `10.1126/sciadv.adi0282`
- **Lokasi**: Nairobi, Kenya (KEMRI / University of Washington)
- **Lisensi**: **CC-BY 4.0** (artikel: *Distributed under a Creative Commons
  Attribution License 4.0*)

| Set | Subjek | TB / non-TB | Rekaman pasif | Peran menurut artikel |
| --- | --- | --- | --- | --- |
| T1 | 90 | 45 / 45 | ± 21.133 | Himpunan **balanced**; dipakai untuk latih + validasi 5-fold |
| T2 | 149 | 103 / 46 | 33.641 | Superset T1; dipakai artikel sebagai **test set** |
| Forced | 149 | 991 / 234 klip | — | Batuk paksa, subset kecil |

Unduh: `python download_tb_screen.py` → 395,4 GB untuk arsip penuh.

#### 1.1.1 Perhatikan perbedaan peran T1 dan T2

Ini mudah disalahpahami dan bisa merusak hasil. Artikel asli menyatakan bahwa T2
dipakai sebagai **test set**: model dilatih pada fold 2–5 dari T1, lalu diuji pada
fold 1 dari T2.

Artinya **T2 bukan kandidat data latih**. Menyerap seluruh T2 akan membuat
angka yang dilaporkan kehilangan makna, karena T2 memang dirancang sebagai
holdout yang tidak pernah disentuh saat-selection model. Kalau butuh lebih
banyak subjek, jalur yang benar adalah menambah sumber data (CODA TB), bukan
menyerap T2 ke latih.

Angka baseline artikel: ResNet18 (ImageNet-pretrained) pada scalogram
mencapai ROC-AUC **0,79 ± 0,06** di T1 dan **0,82 ± 0,03** di T2
(sens 0,70–0,74, spec 0,71–0,72). Angka ini penting sebagai pembanding:
data yang sama mendukung AUROC jauh di atas 0,639 yang dicapai model kita.

### 1.2 CODA TB DREAM (target utama)

- **DOI**: `10.7303/syn31472953` · Synapse folder `syn40358494`
- **Metadata**: `syn41604939`
- **Lisensi**: **CC-BY 4.0** — penggunaan komersial diizinkan
- **Negara**: India, Madagaskar, Filipina, **Afrika Selatan**, Tanzania,
  Uganda, Vietnam

#### 1.2.1 Yang sudah diverifikasi langsung

Diverifikasi lewat API publik Synapse (tanpa token):

- `syn40358494` bernama **`solicited_data`** dan bisa dibaca secara anonim.
- Isinya **9.772 entitas**, seluruhnya `FileEntity`, struktur **datar** (tanpa
  subfolder), bernama `<epoch_ms>-recording-<n>.wav`, misalnya
  `1620627399144-recording-1.wav`.
- `syn41604939` (**metadata**) **tidak** bisa dibaca tanpa autentikasi.

Konsekuensi praktis:

- Nama file **tidak memuat id peserta**, hanya cap waktu. Pemetaan ke peserta
  harus lewat kolom `participant` di `solicited.csv`.
- Karena foldernya datar, `download_coda.py` tidak butuh rekursi untuk bagian
  ini — tetap mendukung rekursi untuk folder visit-control.

#### 1.2.2 Angka dari publikasi (belum diverifikasi di repo ini)

| Partisi | Peserta | Rekaman | Ukuran |
| --- | --- | --- | --- |
| CODA-TB DREAM (publikasi) | 2.143 | 733.756 | ± 745 GB |
| Split latih yang lazim dipakai | 1.105 | — | — |

> Angka 733.756 adalah total dataset DREAM, **bukan** isi `syn40358494`. Folder
> yang terverifikasi berisi 9.772 rekaman. Jangan menulis "733.756 rekaman
> tersedia di folder ini" — itu tidak cocok dengan yang diukur.

#### 1.2.3 Untuk peserta di Indonesia

Tidak ada. CODA-TB tidak memuat peserta dari Indonesia. Lihat §2.

#### 1.2.4 Cara memperoleh akses

1. Buat akun Synapse, selesaikan status *Certified & Validated*.
2. Buka `https://www.synapse.org/Synapse:syn50353157`, setujui syarat.
3. Tulis *Intended Data Use Statement* (maks. 500 kata, bahasa Inggris).
4. Buat personal access token, lalu `export SYNAPSE_AUTH_TOKEN=...`.
5. `python download_coda.py --destination coda-tb --dry-run`, lalu ulangi tanpa
   `--dry-run`.

Skrip menolak berjalan tanpa token, dan menolak menandai metadata "sukses"
bila `clinical.csv`, `additional.csv`, atau `solicited.csv` tidak ditemukan —
layout Synapse yang berubah harus terdeteksi, bukan diteruskan diam-diam.

Untuk menguji tanpa mengunduh 745 GB, pakai `--limit-participants 20`. Batas
itu menghitung **peserta**, bukan file: satu peserta bisa menyumbang puluhan
klip, sehingga pembatas berbasis file akan mengunduh jauh lebih sedikit orang
daripada yang diminta.

---

## 2. Mengapa Indonesia Tidak Ada di `supported_countries`

Tidak ada dataset TB Indonesia yang bisa diakses untuk skrining berbasis suara.
Kenapa ini ditangani secara eksplisit, bukan diabaikan:

- `CODA_TB_COUNTRIES` = negara yang **benar-benar** ada di data pelatihan.
- `UNVALIDATED_COUNTRIES = {"ID"}` = negara yang dituju tim tetapi **tidak**
  punya data. Respons HTTP 422 dengan kode `COUNTRY_NOT_VALIDATED` dan
  penjelasan dalam bahasa Indonesia.
- `AudioRecorder.tsx` menawarkan `ID` sebagai pilihan, jadi penolakan ini akan
  benar-benar terjadi — dan harus informatif, bukan `422` tanpa penjelasan.

Yang **tidak** kami lakukan: melonggarkan gate agar demo terlihat berjalan.
Gate 422 dengan alasan yang jujur lebih berguna daripada angka yang menyesatkan.

---

## 3. Kolom Klinis: Yang Dipakai dan Yang Dilarang

Loader CODA sudah menyediakan variabel yang persis sama dengan formulir web
(16 bidang). `ClinicalPreprocessor` mengubahnya menjadi vektor **27-dim**:
6 numerik ternormalisasi, 9 biner, 1 jumlah klip, 7 one-hot negara, 3 one-hot
HIV.

### 3.1 Larangan keras: kebocoran label

`Metadata.csv` TBscreen memuat kolom yang **mendefinisikan label** itu sendiri:

| Kolom | Masalah |
| --- | --- |
| Xpert grade | Hasil uji diagnostik |
| AFB smear | Hasil uji diagnostik |
| Ct value | Ambang diagnostik molekuler |
| Cavities | Temuan radiologi yang sudah berarti TB |

Kolom-kolom ini **tidak boleh** masuk `ClinicalPreprocessor`. Memasukkannya
akan membuat AUROC melompat ke angka yang tidak mungkin dicapai oleh audio,
dan tidak akan bertahan saat diuji di lapangan. Daftar negara
tidak mencegah hal ini secara otomatis — ini tanggung jawab manusia saat
menambah kolom.

### 3.2 Paritas latih ↔ inferensi

Ada **dua** implementasi encoder di repo:
`training.encoding.ClinicalPreprocessor` (pelatihan) dan
`src.metadata.encode_clinical_metadata` (inferensi). Keduanya harus
menghasilkan vektor yang identik untuk baris yang sama; kalau tidak, model
dilatih pada satu representasi dan dilayani dengan representasi lain.

Untuk itu, `CLINICAL_FEATURE_ORDER` berada di satu konstanta dan Countries
diturunkan dari `CODA_TB_COUNTRIES` — bukan daftar harfian di dua tempat.
Dulu daftar itu berbeda: satu memakai `SA` (Arab Saudi), satu memakai `ZA`
(Afrika Selatan), dan `KE` tidak ada di gate padahal manifest Geralnya
meng condomin `KE`.

### 3.3 Normalisasi hanya dari data latih

`ClinicalPreprocessor.fit()` dipanggil **hanya pada partisi latih**
di dalam `run_cross_validation`. Statistik dari seluruh kohort akan
membocorkan mean dan standard deviation test-fold ke fase latih.

---

## 4. "From scratch": apa yang sebenarnya berarti di kode

Proyek ini memang dilatih dari nol, dan itu terbukti di 4 titik:

| Lokasi | Bukti |
| --- | --- |
| `src/model.py:1-4` | hanya mengimpor `torch` — tanpa `transformers` |
| `training/cross_validate.py` | `initialization="random_pytorch_default"` |
| `training/train.py` | `pretrained_weights=False` |
| `training/artifact_manifest.py` | menolak manifest yang tidak mendeklarasikan keduanya |

Tapi "from scratch" adalah **pilihan metodologis**, bukan syarat mutlak.
Rekomendasi (lihat `docs/RESEARCH_ROADMAP.md` §2.3): memindahkan batas
tersebut lewat **distillation** — guru pretrained dibekukan, hanya membentuk
gradien, lalu dibuang. Student tetap `random_pytorch_default` dan artifact
tetap ±1,2 MB, sehingga klaim "from scratch pada student" tetap benar.

`pretrained_weights` pada manifest selalu merujuk **artifact yang
dipasang**, bukan model yang pernah demisewa. Guru tidak pernah sampai ke
produksi, jadi tidak pernah ada bobot pretrained yang tersembunyi.

---

## 5. Anti-kebocoran checklist

Sebelum melaporkan angka baru, pastikan semua ini benar:

- [x] Split per **pasien**, bukan per rekaman
- [ ] `ClinicalPreprocessor.fit()` hanya dari partisi latih
- [ ] Tidak ada kolom label-defining di preprocessor klinis
- [ ] Ambang dipilih dari validation, bukan dari test
- [ ] Encoder latih dan inferensi menghasilkan vektor identik
- [ ] Angka dilaporkan bersama confidence interval dan ukuran test set
- [ ] Embargo test yang benar-benar tidak disentuh
- [ ] `evaluation_gate` tetap `blocked` sampai ada validasi eksternal

---

## 6. Rujukan

- Sharma et al., *Science Advances* 2024 — TBscreen (Zenodo 10431329)
- CODA TB DREAM — Synapse `syn40358494`, DOI `10.7303/syn31472953`
- arXiv 2509.09746 — Zambia, Wav2Vec2 + klinis → AUROC 0,921
- arXiv 2508.02741 — DeepGB-TB, 7 negara → AUROC 0,903
- arXiv 2606.17337 — CODA, perbandingan embedding
- *Sensors* 2026, 26(4):1223 — PPV/NPV pada prevalensi kohort
