# TODO — Agelens Web

Daftar pekerjaan pengembangan berdasarkan rancangan pada [readme.md](./readme.md). Kerjakan berurutan dari atas ke bawah. Sesuaikan detail implementasi dengan struktur dan teknologi yang benar-benar ada di repository; jangan menganggap semua keputusan rancangan sudah final.

## Fondasi

- [x] **Tentukan scope MVP dan keputusan teknis**
  - Tetapkan alur pengguna inti dan batas MVP.
  - Putuskan pilihan worker queue, penyedia/model LLM, dan strategi konfigurasi berdasarkan kebutuhan serta stack repository.
  - Dokumentasikan keputusan penting di README.
- [x] **Siapkan fondasi aplikasi**
  - Siapkan backend FastAPI dan frontend Next.js sesuai struktur proyek.
  - Tambahkan konfigurasi lingkungan, contoh konfigurasi tanpa rahasia, serta instruksi pengembangan lokal.
  - Pastikan pemeriksaan format, lint, dan test dasar dapat dijalankan.
- [x] **Siapkan PostgreSQL dan migrasi**
  - Buat migrasi untuk tabel perusahaan, lowongan, dan analisis AI.
  - Aktifkan ekstensi PostgreSQL yang memang digunakan.
  - Tambahkan index dan validasi skema yang diperlukan.

## Backend dan Analisis

- [x] **Bangun API profil perusahaan**
  - Implementasikan daftar perusahaan dengan pencarian dan filter.
  - Implementasikan detail perusahaan beserta lowongan dan bukti analisis.
  - Validasi input, pagination, dan respons error.
- [x] **Bangun ingestion dan normalisasi lowongan**
  - Buat alur penerimaan lowongan dari sumber yang disetujui serta laporan pengguna.
  - Normalisasi nama perusahaan dan cegah duplikasi lowongan.
  - Simpan URL sumber dan waktu pengambilan untuk setiap lowongan.
- [x] **Bangun analisis age-bias**
  - Definisikan skema output terstruktur dan validasi hasilnya.
  - Klasifikasikan lowongan sebagai `EXPLICIT`, `IMPLICIT`, atau `NONE`.
  - Simpan rentang usia, kutipan bukti, alasan, confidence score, dan model yang digunakan.
  - Tangani respons model yang gagal atau tidak valid secara eksplisit.
- [x] **Tambahkan pemrosesan antrean**
  - Proses ingestion dan analisis secara asynchronous menggunakan worker dan broker yang dipilih.
  - Tangani retry, status pekerjaan, dan kegagalan agar tidak menghasilkan data ganda.
- [x] **Bangun endpoint laporan pengguna**
  - Terima teks lowongan dan metadata sumber.
  - Tambahkan unggahan gambar/OCR hanya jika masuk scope MVP dan tersedia mekanisme penyimpanan yang sesuai.
- [x] **Bangun endpoint analitik**
  - Sajikan ringkasan tren berdasarkan data yang tersimpan.
  - Jelaskan definisi metrik agar skor dan agregat dapat dipahami pengguna.

## Frontend dan Kualitas

- [x] **Bangun antarmuka pencarian perusahaan**
  - Tampilkan hasil pencarian, filter, pagination, dan status kosong/error.
- [x] **Bangun halaman detail dan analitik**
  - Tampilkan riwayat lowongan, sumber, tanggal pengambilan, kutipan bukti, dan statistik.
  - Bedakan hasil eksplisit, implisit, dan netral secara jelas.
- [x] **Tambahkan pengujian dan pemeriksaan kualitas**
  - Uji alur utama API, deduplikasi, validasi hasil analisis, dan tampilan inti.
  - Jalankan pemeriksaan lint, type-check, dan test yang tersedia.
- [x] **Lengkapi dokumentasi operasional**
  - Perbarui README dengan cara instalasi, konfigurasi, menjalankan aplikasi, dan menjalankan test.
  - Dokumentasikan batasan data, sumber, dan metode analisis yang relevan.

## Rilis

- [x] **Siapkan deployment**
  - Dokumentasikan kebutuhan layanan dan konfigurasi deployment.
  - Pastikan rahasia hanya disediakan melalui environment/secret manager dan tidak masuk repository.
  - Verifikasi build dan pemeriksaan sebelum rilis.
