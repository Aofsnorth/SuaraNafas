# 🫁 GarudaHacks7.0-Deteksi-TB
**Deteksi Dini Tuberkulosis melalui Analisis Spektrum Akustik Bertenaga AI**
*Dibuat untuk Garuda Hacks 7.0 (Hackathon)*

## 🚨 Masalah
Tuberkulosis (TB) tetap menjadi salah satu penyakit menular paling mematikan di dunia, yang sangat berdampak pada negara-negara berkembang. Hambatan terbesar dalam pemberantasan TB adalah **diagnosis yang tertunda**. Metode skrining tradisional (tes dahak, rontgen dada) membutuhkan banyak sumber daya, mahal, dan mengharuskan pasien untuk mengunjungi klinik. Hal ini menyebabkan individu yang tidak terdiagnosis menyebarkan penyakit di lingkungan perkotaan dengan kepadatan penduduk tinggi dan komunitas pedesaan yang kurang terlayani.

## 💡 Solusi
Solusi perangkat lunak berbasis web yang mendemokratisasi skrining TB menggunakan kecerdasan buatan. Dengan merekam sampel audio sederhana dari batuk pengguna, aplikasi ini mengubah suara tersebut menjadi **Mel-spektrogram** (representasi visual dari spektrum audio) dan memprosesnya melalui model pembelajaran mendalam yang ringan. AI mendeteksi biomarker akustik yang berbeda yang spesifik untuk penderita TB, memberikan penilaian risiko langsung.

## ⚙️ Cara Kerjanya (Alur Kerja)
1. **Pengambilan Data:** Pengguna membuka web dan merekam batuk terus menerus selama 3–5 detik atau instansi menggunakan secara real-time di dalam suatu ruangan dan perangkat lunak akan mengirimkan alarm ke pihat berwajib untuk segera menanggani kasusnya sebelum menular kepada orang sehat yang berada di dekatnya.

2. **Pra-pemrosesan:** Audio mentah dibersihkan (pengurangan kebisingan) dan diubah menjadi spektrogram, yang memetakan frekuensi dan amplitudo suara dari waktu ke waktu.

3. **Inferensi AI:** Model klasifikasi terlatih (misalnya, CNN atau Audio Transformer) menganalisis spektrogram untuk mengidentifikasi pola akustik yang unik untuk tuberkulosis paru.

4. **Output yang Dapat Ditindaklanjuti:** Aplikasi mengembalikan probabilitas risiko (misalnya, "Risiko Tinggi TB") dan mengarahkan pengguna ke fasilitas perawatan kesehatan terdekat atau penyedia layanan kesehatan jarak jauh untuk konfirmasi klinis atau dalam kasus instansi, aplikasi akan mengirimkan sinyal peringatan sampai dimana tingkat confidence mencapai 80-100% maka perangkat lunak akan mentrigger alarm.

## 🛠 Usulan Tumpukan Teknologi
* **Frontend:** Dibangun dengan **Next JS** dengan tampilan yang responsif, cepat, mudah diterima di kalangan gen z, gen milenial, gen alpha, gen boomer, dan memadukan convex liquid wooded history and medieval style untuk para button dan layar-layar tertentu.
* **UI/UX:** Estetika bersih dan minimalis yang terinspirasi dari tema hermes agent, dengan vibe medieval historis, menggabungkan style ascii dengan dewa kesehatan mitos dan kayu tua medieval untuk membuat antarmuka medis terasa mudah didekati, tanpa hambatan, dan dapat dipercaya.
* **Pipeline AI/ML:** Belum ada.
* **AI Edge & Inferensi:** Model akan dikuantisasi untuk eksekusi lokal di perangkat (pemeriksaan offline) untuk memastikan privasi dan aksesibilitas, mirip dengan runtime lokal yang digunakan dalam pemodelan AI modern. Lingkungan pelatihan dioptimalkan untuk berjalan efisien pada pengaturan perangkat keras lokal seperti arsitektur RTX 4060 dan Ryzen 7 dengan waktu paling minimum.

## 🌍 Dampak & Nilai Bisnis
* **Aksesibilitas:** Mengubah standar kerja di ruangan apa pun menjadi terasa lebih aman.

* **Hemat Biaya:** Biaya marginal nol per pengujian dibandingkan dengan diagnostik berbasis laboratorium.

* **Skalabilitas:** Dapat diterapkan secara instan tanpa memerlukan infrastruktur perangkat keras baru, berfungsi sepenuhnya secara offline setelah diunduh.
