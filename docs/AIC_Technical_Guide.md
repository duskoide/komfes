# AI Innovation Challenge (AIC) — Panduan Teknis

> **Sumber:** diekstrak dari [`AI_Innovation_Challenge.md`](./AI_Innovation_Challenge.md)
> (bagian *Teknis & Kriteria* dan *Kriteria Penilaian*).
> Dokumen ini hanya memuat aspek teknis kompetisi. Untuk aturan umum, pendaftaran, jadwal,
> dan kontak, lihat dokumen rulebook lengkap.
> Diselenggarakan oleh **COMPFEST 18** · Kolaborasi dengan **WIZ.AI**.

---

## Daftar Isi

1. [Tema & Ruang Lingkup](#tema--ruang-lingkup)
2. [Ringkasan Alur Teknis](#ringkasan-alur-teknis)
3. [Ketentuan Produk](#ketentuan-produk)
4. [Batasan Ruang Lingkup MVP](#batasan-ruang-lingkup-mvp)
5. [Deliverables Penyisihan](#deliverables-penyisihan)
6. [Struktur Proposal](#struktur-proposal)
7. [Video Proof of Work](#video-proof-of-work)
8. [Video Promosi Karya Inovasi](#video-promosi-karya-inovasi)
9. [Standar Pengembangan (Git & Repo)](#standar-pengembangan-git--repo)
10. [Ketentuan Tambahan](#ketentuan-tambahan)
11. [Teknis Babak Final](#teknis-babak-final)
12. [Kriteria Penilaian](#kriteria-penilaian)

---

## Tema & Ruang Lingkup

Tema: **AI for the Backbone of the Economy** — solusi AI pada rantai pasok pasca-produksi primer:

1. **Smart Manufacturing (Pabrik):** AI di proses pengolahan dan operasi pabrik.
2. **Smart Logistics (Gudang & Distribusi):** AI di pergerakan barang.
3. **Smart Commerce (Toko & Pasar):** AI pada konsumen, sales operasional, serta transaksi
   komersial.

Bentuk inovasi: aplikasi web, IoT, dan software/hardware lain yang mengintegrasikan AI.

---

## Ringkasan Alur Teknis

| Tahap | Tanggal (2026) | Keterangan |
|-------|----------------|------------|
| Periode pengerjaan (Asynchronous) | 17 Juni – 25 Agustus | Pengembangan proyek |
| AIC Talks | 25 Juli | Talk show wawasan AI |
| **Deadline submisi penyisihan** | **25 Agustus, 23.55 WIB** | Via situs COMPFEST |
| Standby Discord (klarifikasi/live demo) | 9 & 10 September, 20.00 | Jawab maks. 2 jam setelah pesan |
| Mentoring (daring) | 20 September | Tidak mempengaruhi penilaian |
| Hackathon (luring, 10 jam) | 26 September | Gedung baru Fasilkom UI |
| Live Pitching (luring) | 27 September | Gedung Fasilkom UI |

- **8 tim terbaik** maju ke tahap final.
- **30 tim pendaftar pertama** mendapat bantuan resource berupa VPS/GPU Credits gratis.

---

## Ketentuan Produk

- Proyek merupakan inovasi di bidang *AI for Backbone Economy* memanfaatkan teknologi AI.
- Merupakan **karya orisinal tim**.
- **Hanya dikerjakan selama periode lomba** (17 Juni – 25 Agustus 2026 pukul 23.55 WIB).
- Proyek penyisihan **wajib dilanjutkan** ke tahap Final.
- **Dilarang** melanjutkan proyek yang sudah pernah dikerjakan di luar periode penyisihan
  (baik yang sudah selesai maupun belum).

---

## Batasan Ruang Lingkup MVP

Ruang lingkup proyek tahap penyisihan **WAJIB HANYA SAMPAI** batasan berikut (menjaga fokus &
reprodusibilitas lokal):

### 1. Frontend (FE) / Antarmuka
- UI fokus pada **alur interaksi inti**: menerima input tunggal dari pengguna dan menampilkan
  output AI.
- **Tidak perlu** membangun: dashboard analitik tingkat lanjut, sistem otentikasi kompleks,
  atau halaman riwayat penggunaan.

### 2. Backend (BE) & Integrasi
- Arsitektur backend cukup sampai **pemrosesan interaksi sinkron**.
- **Tidak perlu**: background jobs, pipeline pencatatan data otomatis (*automated data
  logging*), atau infrastruktur database terdistribusi.
- Fokuskan agar API/sistem dapat dijalankan sesuai panduan `README.md` menggunakan
  `docker compose`.

### 3. Model AI & Algoritma
- Implementasi AI fokus pada **fungsi inferensi utama (*core inference*)** dengan parameter
  **statis** agar demonstrasi berjalan.
- **Tidak diminta** menyertakan: sistem penalaan otomatis (*auto-tuning*), skrip pengujian
  massal (*bulk testing*), atau mekanisme loop umpan balik otomatis pada repository tahap
  penyisihan.

---

## Deliverables Penyisihan

| Item | Spesifikasi |
|------|-------------|
| **Repository GitHub** | Visibility **public**, berisi setup guide jelas di `README.md` + `docker compose` |
| **Video Proof of Work** | Maks **7 menit**, YouTube **unlisted**, nama: `COMPFEST 18 AIC: PROOF OF WORK - [Nama Tim] - [Nama Proyek]` |
| **Video Karya Inovasi** | Maks **5 menit**, YouTube **public**, nama: `COMPFEST 18 AIC: [Nama Tim] - [Nama Proyek]` |
| **Proposal (PDF)** | Maks **20 halaman** (tidak termasuk cover, daftar pustaka, lampiran) |

Aturan teknis deliverables:

- Commit & push ke GitHub (visibility **public**) **setiap** membuat perubahan.
- Batas commit/push terakhir: **sebelum 25 Agustus 2026 pukul 23.55 WIB**.
- Deadline pengumpulan semua berkas: **25 Agustus 2026 pukul 23.55 WIB**, submisi via situs
  COMPFEST.
- **Dataset** boleh dari sumber publik yang sudah tersedia atau data sintetik. Namun penggunaan
  model (karya pihak luar maupun bukan), arsitektur sistem, hingga fitur **harus dilakukan dan
  dijelaskan bersamaan preprocessing-nya selama periode lomba**.
- Boleh memakai **model API** dan **pre-trained model**; model **wajib di-*fine tune*** sesuai
  inovasi fitur per tim.

---

## Struktur Proposal

Proposal PDF (maks 20 halaman) terdiri setidaknya atas:

1. Nama Kelompok dan Judul/Nama Inovasi
2. Latar Belakang
3. Tujuan dan Manfaat Pengembangan
4. **Metodologi**, berisikan:
   - Alur memperoleh dataset
   - Alur pengembangan model (tiap feature)
   - Alur integrasi model ke environment kode
   - Metode lain yang mendukung alasan pengambilan keputusan dalam pengembangan
5. Kesimpulan

---

## Video Proof of Work

- **HANYA** menunjukkan jalannya MVP + penjelasan apa yang dilakukan.
- Menggambarkan **kondisi/status MVP terakhir** saat dikumpulkan (di-*cross check* panitia).
- Menunjukkan flow program yang sudah working **atau** belum/buggy, dengan penjelasan status
  tiap fitur.
- **Semua fitur** yang ditunjukkan di video inovasi **harus ada** di video proof of work.
- Durasi maks **7 menit**.

Ketentuan demonstrasi per jenis produk:

- **Software only:** double screen (terminal + aplikasi) + timestamp. Boleh *fast-forward* saat
  menunggu fitur load + voice over. **DILARANG KERAS** memotong (cut) video / editing lain.
- **Hardware integrated software:** wajib punya ***mock data mode*** (software jalan tanpa
  hardware) untuk cross check panitia. Video: double screen terminal + aplikasi + timestamp +
  hardware yang bekerja. Jika belum fully integrated, boleh hanya mock data mode. Boleh
  *fast-forward* + voice over. **DILARANG KERAS** memotong (cut) video / editing lain.

Unggah ke YouTube **unlisted**, nama:
`COMPFEST 18 AIC: PROOF OF WORK - [Nama Tim] - [Nama Proyek]`

---

## Video Promosi Karya Inovasi

- Menggambarkan **proses perancangan karya**.
- Menjelaskan **bagaimana inovasi menyelesaikan masalah** yang diangkat tim.
- Disajikan menggugah antusiasme **pengguna baru & minat investor**.
- Demonstrasi via screen recording atau rekaman kamera.
- Format **MP4**, resolusi minimal **720p**, durasi maks **5 menit**.
- Unggah ke YouTube **public**, nama:
  `COMPFEST 18 AIC: [Nama Tim] - [Nama Proyek]`

---

## Standar Pengembangan (Git & Repo)

- Kode di GitHub harus **dapat diakses dan dioperasikan**.
- Setiap perubahan wajib disertai pesan commit deskriptif mengikuti **Conventional Commits**:
  - `feat: <deskripsi>` — penambahan fitur/fungsionalitas baru
  - `fix: <deskripsi>` — perbaikan bug/kesalahan pada sistem
  - `refactor: <deskripsi>` — perubahan struktur kode tanpa mengubah fungsionalitas
  - Commit tanpa pesan deskriptif / di luar konvensi dapat dianggap **tidak memenuhi standar**.
  - Referensi: https://www.conventionalcommits.org
- Setup guide di `README.md` harus cukup jelas agar panitia dapat menjalankan aplikasi secara
  **lokal**.

---

## Ketentuan Tambahan

- Video menunjukkan **use case aplikasi** dan **teknologi AI** yang digunakan.
- Proposal lengkap dan **bebas plagiarisme**.
- **Dilarang** menunjukkan latar belakang institusi pendidikan dalam bentuk apapun.
- Panitia berhak menindak indikasi kecurangan, termasuk meminta penjelasan / **live demo** pada
  periode penjurian.
- Peserta **standby Discord 9 & 10 September 2026 pukul 20.00**; panitia dapat meminta
  klarifikasi/penjadwalan live demo. Pesan dikirim tepat waktu; peserta boleh menjawab hingga
  **maks 2 jam** setelah pesan dikirim.
- Submisi boleh lebih dari satu kali; penilaian hanya pada **submisi terakhir**.
- Tidak mengumpulkan submisi hingga batas akhir = tim dianggap **mengundurkan diri**.
- Panitia berhak **mendiskualifikasi** bila poin belum lengkap, terutama link video proof of
  work & source code.

---

## Teknis Babak Final

Terdiri atas **mentoring, hackathon, dan live pitching**. Hackathon adalah inti babak final.

- **Hackathon 10 jam non-stop**, seluruh finalis bersamaan di lokasi yang ditentukan.
- Finalis melakukan **push berkala** sesuai checkpoint agar panitia dapat memantau
  perkembangan tiap tim.
- Setelah hackathon berakhir, finalis **dilarang keras** mengubah repository dalam bentuk
  apapun.
- Hasil tidak wajib di-*deploy* ke cloud, tetapi harus **siap didemonstrasikan lokal
  (localhost)** di hadapan juri pada Live Pitching.
- **Hardware** (jika ada) sepenuhnya tanggung jawab tim; panitia tidak menyediakan hardware.
  Tim wajib mendaftarkan spesifikasi perangkat paling lambat saat **Technical Meeting Babak
  Final** dan memastikan perangkat mematuhi regulasi keamanan venue.
- Detail final diumumkan pada Technical Meeting Babak Final.

---

## Kriteria Penilaian

### Teknis Penyisihan

| Kriteria | Bobot | Poin Penilaian |
|----------|-------|----------------|
| **Orisinalitas dan Dampak Sosial** | `[?]` | Keunikan & inovasi solusi; pendekatan baru; pembeda dari solusi existing; relevansi konteks; dampak bagi individu/pertumbuhan bisnis; urgensi masalah; kesesuaian kebutuhan target pengguna; potensi kebutuhan global. |
| **Implementasi Teknologi & Kematangan Arsitektur** | `[?]` | Kesesuaian & proporsionalitas pemilihan teknologi (model AI, framework, stack); AI fokus pada core inference bersih dengan parameter jelas; modularitas arsitektur (AI/backend/frontend terpisah); kecukupan dokumentasi teknis (README). |
| **Kesiapan MVP untuk Babak Final** | 15% | Ruang lingkup MVP tepat (tidak over/underbuilt); fungsionalitas inti cukup untuk dievaluasi & dikembangkan; arsitektur fleksibel tanpa perombakan total; area yang diakui tim masih dapat ditingkatkan. |
| **Video Promosi** | 15% | Komunikasi masalah & solusi AI dengan bahasa lugas; storytelling proses perancangan; daya tarik bagi stakeholders (pemerintah, industri); kelengkapan konten sesuai ketentuan. |
| **Kualitas Proposal & Proses Pengembangan** | 15% | Struktur & kelengkapan proposal (metodologi, alur dataset, alur integrasi model); kejelasan & kelogisan metodologi/argumentasi teknis; decision making berbasis data/analisis; cerita pengembangan iteratif & reflektif. |
| **Relevansi dengan Tema** | 10% | Kesesuaian inovasi dengan tema; penggunaan AI relevan & tidak dipaksakan. |
| **Business Value dan Governance** *(BONUS)* | 3.5% | Model bisnis/analisis kelayakan adopsi industri realistis; pertimbangan regulasi AI, etika, prinsip sistem cerdas bertanggung jawab. |
| **AIC Talks** *(BONUS)* | 1.5% | Mengikuti & mengisi presensi AIC Talks. |
| **TOTAL** | **105%** | (termasuk komponen bonus) |

> **Catatan OCR:** bobot "Orisinalitas dan Dampak Sosial" serta "Implementasi Teknologi &
> Kematangan Arsitektur" tidak terbaca pada dokumen sumber (`[?]`). Total tertera 105%
> (termasuk bonus). Konfirmasi ke panitia bila nilai pasti diperlukan.

---

*© COMPFEST — #EncloseTheGap*
