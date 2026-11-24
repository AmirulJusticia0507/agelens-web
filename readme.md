# Agelens Web

> Dokumentasi rancangan sistem untuk mendeteksi pembatasan usia pada lowongan kerja di Indonesia.

## Daftar Isi

- [Latar Belakang](#latar-belakang)
- [Tujuan Sistem](#tujuan-sistem)
- [Scope MVP dan Keputusan Teknis](#scope-mvp-dan-keputusan-teknis)
- [Tech Stack](#tech-stack)
- [Menjalankan Secara Lokal](#menjalankan-secara-lokal)
- [System Design](#system-design)
- [Arsitektur Data Pipeline](#arsitektur-data-pipeline)
- [Logika Deteksi Age-Bias](#logika-deteksi-age-bias)
- [Skema Database](#skema-database)
- [Output Analisis AI](#output-analisis-ai)
- [Endpoint API](#endpoint-api)
- [Tantangan dan Mitigasi](#tantangan-dan-mitigasi)

## Latar Belakang

Proyek ini relevan dengan kondisi rekrutmen di Indonesia, di mana batasan usia seperti:

- Maksimal 25 tahun
- Maksimal 27 tahun
- Maksimal 30 tahun

dapat menjadi penghalang bagi pelamar yang berusia 30 tahun ke atas, meskipun usia tersebut sering kali disertai dengan kematangan profesional dan produktivitas tinggi.

## Tujuan Sistem

Agelens Web dirancang sebagai indeks transparansi pasar kerja yang dapat:

- Mengumpulkan lowongan kerja dari berbagai sumber.
- Mendeteksi pembatasan usia secara eksplisit maupun implisit.
- Menyimpan bukti kutipan dari lowongan yang dianalisis.
- Menampilkan profil perusahaan beserta tren age-bias-nya.
- Menyediakan data yang dapat ditelusuri kembali ke sumber asli.

PostgreSQL digunakan sebagai database utama dengan memanfaatkan:

- **JSONB** untuk menyimpan payload mentah hasil scraping.
- **pgvector** sebagai dasar pencarian kemiripan semantik pada tahap lanjutan.
- **pg_trgm** untuk pencocokan nama perusahaan.

Arsitektur ini menjaga stack tetap ringkas tanpa perlu menambahkan database NoSQL atau vector database terpisah.

## Scope MVP dan Keputusan Teknis

MVP berfokus pada alur yang dapat diverifikasi dari awal hingga akhir:

1. Pengguna mengirim teks lowongan dan informasi sumber.
2. Sistem menyimpan lowongan dan menganalisis indikasi pembatasan usia.
3. Pengguna mencari perusahaan dan memeriksa lowongan beserta bukti sumbernya.
4. Dashboard menampilkan ringkasan statistik dari data yang sudah dianalisis.

Untuk menjaga MVP tetap terukur, scraping terjadwal, unggahan gambar/OCR, dan deployment produksi bukan bagian dari alur awal. Sumber lowongan harus tetap tercatat agar hasil dapat ditelusuri; analisis bukan penilaian hukum atau klaim definitif mengenai perusahaan.

| Keputusan | Pilihan MVP | Alasan |
| --- | --- | --- |
| API backend | FastAPI | Konsisten dengan rancangan awal dan mendukung validasi skema API |
| Database | PostgreSQL 17, migrasi Alembic | Mendukung relasi, JSONB, dan ekstensi yang direncanakan |
| Analisis teks | Adapter LLM dengan endpoint OpenAI-compatible yang dikonfigurasi melalui environment | Tidak mengunci implementasi ke satu vendor; kegagalan konfigurasi atau provider harus terlihat jelas |
| Antrean | ARQ dengan Redis untuk pekerjaan analisis asynchronous | Menggunakan worker Python async yang ringan dan terintegrasi dengan Redis |
| Frontend | Next.js App Router, TypeScript, Tailwind CSS | Mengikuti stack rancangan dan mendukung halaman pencarian serta detail |
| Sumber lowongan | Laporan teks pengguna pada MVP | Menghindari ketergantungan awal pada scraper lintas platform |
| Gambar dan OCR | Ditunda setelah MVP | Memerlukan penyimpanan file dan evaluasi OCR tersendiri |

## Tech Stack

| Layer | Teknologi | Alasan |
| --- | --- | --- |
| Backend dan AI worker | Python, FastAPI, ARQ | Ekosistem AI/NLP yang matang, dokumentasi API otomatis, dan worker asynchronous berbasis Redis |
| Scraper engine | Playwright atau Crawl4AI (tahap lanjutan) | Mendukung portal yang merender halaman secara client-side; scraping tidak termasuk scope MVP |
| Database | PostgreSQL 17 dengan JSONB dan pgvector | Menyimpan data relasional, payload mentah, serta embedding teks |
| Frontend | Next.js App Router, TypeScript, Tailwind CSS | Mendukung SEO, SSR, dashboard pencarian, dan visualisasi data |
| Message broker | Redis | Memisahkan antrean scraping dan pemanggilan API LLM dari server utama |

## Menjalankan Secara Lokal

### Prasyarat

- Python 3.12 atau lebih baru
- Node.js 20.9 atau lebih baru
- Docker Desktop atau PostgreSQL 17 dengan ekstensi `pg_trgm` dan `vector`
- Redis diperlukan saat pemrosesan antrean digunakan

### Database

```powershell
Copy-Item .env.example .env
docker compose up -d db
Set-Location backend
..\.venv\Scripts\alembic.exe upgrade head
```

`.env.example` berisi kredensial khusus pengembangan lokal. Ganti nilainya untuk lingkungan non-lokal dan jangan commit file `.env`.

Compose memetakan container database ke host port `5437` (dapat diubah melalui `POSTGRES_PORT`) agar tidak bentrok dengan PostgreSQL lokal atau project lain di port `5432`-`5436`. `DATABASE_URL` harus memakai port yang sama.

Migrasi membuat tabel `companies`, `job_postings`, dan `ai_age_analyses` beserta ekstensi `pg_trgm` (pencarian nama perusahaan), `pgcrypto` (`gen_random_uuid()`), dan `vector` (embedding tahap lanjutan). Untuk memeriksa dan membatalkan migrasi:

```powershell
..\.venv\Scripts\alembic.exe current
..\.venv\Scripts\alembic.exe downgrade base
```

Migrasi mencakup tabel `companies`, `job_postings`, dan `ai_age_analyses` sesuai model di `app/db/models.py`, dengan index dan validasi berikut.

| Objek | Fungsi |
| --- | --- |
| `ix_companies_normalized_name_trgm` | Pencarian nama perusahaan berbasis `pg_trgm` (`gin_trgm_ops`) |
| `ix_companies_display_name_fts` | Full-text search nama tampilan dengan konfigurasi bahasa `indonesian` |
| `ix_companies_age_bias_score` | Urutan daftar perusahaan berdasarkan `age_bias_score` menurun |
| `ix_ai_age_analyses_max_age` | Filter batas usia maksimal, hanya untuk baris dengan `max_age` terisi |
| `ck_companies_age_bias_score_range` | `age_bias_score` dibatasi `0`-`100` |
| `ck_ai_age_analyses_restriction_type` | `restriction_type` hanya `EXPLICIT`, `IMPLICIT`, atau `NONE` |
| `ck_ai_age_analyses_confidence_score_range` | `confidence_score` dibatasi `0`-`1` |
| `ck_ai_age_analyses_age_range` | `min_age` tidak boleh lebih besar dari `max_age` |
| `UNIQUE(content_hash)` | Mencegah lowongan identik tersimpan dua kali |
| `UNIQUE(job_posting_id)` pada analisis | Satu lowongan hanya memiliki satu hasil analisis |

Lowongan yang terhubung ke perusahaan menggunakan `ON DELETE SET NULL` agar bukti lowongan tidak hilang saat data perusahaan dihapus, sedangkan analisis dihapus bersama lowongannya (`ON DELETE CASCADE`). Test integrasi `tests/test_postgres_migrations.py` memeriksa index dan constraint di atas; test dilewati otomatis jika database tidak dapat dijangkau.

### Backend

Dari root repository, jalankan di PowerShell:

```powershell
python -m venv .venv
Set-Location backend
..\.venv\Scripts\python.exe -m pip install -e ".[dev]"
..\.venv\Scripts\alembic.exe upgrade head
..\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir . --reload
```

API tersedia di `http://localhost:8000`; dokumentasi interaktif ada di `http://localhost:8000/docs`. Pemeriksaan health: `GET /api/v1/health`.

### Antrean Analisis

Analisis lowongan dijalankan oleh worker ARQ menggunakan Redis. Pastikan `REDIS_URL` di `.env` menunjuk ke Redis Compose (default `redis://localhost:6380/0`), lalu nyalakan layanan:

```powershell
docker compose up -d db redis
```

Jalankan worker dari direktori `backend` di terminal terpisah:

```powershell
..\.venv\Scripts\arq.exe app.worker.WorkerSettings
```

Lowongan baru masuk antrean dengan status `pending`; worker memperbarui status menjadi `processing`, lalu `completed` atau `failed`. Kegagalan sementara dicoba ulang secara terbatas, dan ID job deterministik mencegah pengiriman job analisis ganda untuk lowongan yang sama.

Untuk menjalankan test backend dari direktori `backend`:

```powershell
..\.venv\Scripts\python.exe -m pytest
```

### Frontend

Di terminal lain dari root repository:

```powershell
Set-Location frontend
Copy-Item .env.example .env.local
npm install
npm run dev
```

Frontend tersedia di `http://localhost:3000`. Salin `.env.example` di root menjadi `.env` untuk konfigurasi backend lokal setelah layanan database, Redis, dan analisis dikembangkan.

## System Design

Bagian ini menggambarkan arsitektur target setelah komponen ingestion dan scraping lanjutan tersedia. Scope MVP saat ini dijelaskan pada [Scope MVP dan Keputusan Teknis](#scope-mvp-dan-keputusan-teknis).

### Alur Tingkat Tinggi

```text
Sumber Lowongan
    |
    v
Ingestion / Scraper
    |
    v
Pembersihan dan Deduplication
    |
    v
Ekstraksi dan Scoring AI
    |
    v
Verifikasi dan Penyimpanan PostgreSQL
    |
    v
API dan Dashboard Frontend
```

### Komponen Utama

#### 1. Ingestion

Worker mengumpulkan data secara terjadwal melalui:

- Job portal seperti JobStreet, Glints, Kalibrr, dan LinkedIn.
- Situs karier perusahaan.
- Media sosial.
- Laporan crowdsourcing berupa teks atau screenshot lowongan.

#### 2. Preprocessing dan Deduplicasi

Teks lowongan dibersihkan terlebih dahulu. Sistem kemudian melakukan:

- Penghitungan hash SHA-256 untuk mendeteksi lowongan yang identik.
- Pencocokan embedding di PostgreSQL untuk mendeteksi lowongan yang memiliki makna serupa.
- Normalisasi nama perusahaan sebelum data disimpan.

#### 3. Ekstraksi dan Penilaian AI

Deskripsi lowongan dikirim ke LLM menggunakan structured output dalam format JSON. Model dapat dijalankan:

- Melalui API penyedia LLM.
- Secara lokal menggunakan model seperti Qwen atau Llama melalui Ollama.

#### 4. Penyimpanan dan Presentasi

Hasil analisis disimpan di PostgreSQL, kemudian ditampilkan melalui API dan dashboard. Pengguna dapat:

- Mencari nama perusahaan.
- Melihat riwayat lowongan.
- Memantau tren batasan usia per industri.
- Menemukan perusahaan yang age-inclusive.

## Arsitektur Data Pipeline

1. **Collector**
   - Mengambil lowongan dari sumber terjadwal.
   - Menerima laporan pengguna sebagai teks atau gambar.

2. **Preprocessing dan Deduplication**
   - Membersihkan teks dan metadata.
   - Menggunakan hash atau kesamaan vektor untuk menghindari pencatatan ganda.

3. **AI Extraction dan Scoring**
   - Mengidentifikasi pembatasan usia.
   - Menghasilkan tipe restriksi, rentang usia, bukti, serta confidence score.

4. **Verification dan Storage**
   - Menyimpan hasil ekstraksi dan bukti kutipan ke PostgreSQL.
   - Memperbarui skor age-bias perusahaan.

5. **Presentation**
   - Menyajikan profil perusahaan dan statistik analitik.

### Ingestion MVP

Layanan backend `ingest_job_posting` menormalisasi nama perusahaan, menghitung hash SHA-256 dari nama perusahaan, judul, dan deskripsi, lalu menyimpan lowongan yang belum pernah diterima. Pencocokan nama menggunakan `pg_trgm`; jika kandidat serupa ambigu, sistem membuat record perusahaan baru daripada menggabungkan secara spekulatif. Pengiriman lowongan identik mengembalikan record yang sudah ada.

## Logika Deteksi Age-Bias

AI mengklasifikasikan hasil analisis ke dalam tiga kategori.

### Explicit Age Cap

Pembatasan usia dinyatakan secara tegas.

Contoh:

- Usia maksimal 27 tahun.
- Maksimal 30 tahun.

### Implicit Age Bias

Pembatasan tidak menyebutkan angka secara langsung, tetapi menggunakan frasa yang dapat menyaring kandidat senior.

Contoh:

- Fresh graduate diprioritaskan.
- Berjiwa muda.
- Maksimal pengalaman 1 tahun untuk posisi mid-level.

### Age-Inclusive atau Neutral

Lowongan tidak mencantumkan batas usia dan lebih berfokus pada kompetensi.

## Skema Database

Model SQLAlchemy berada di `backend/app/db/models.py`, sedangkan migrasi Alembic di `backend/migrations/versions/` adalah sumber skema yang dijalankan. UUID dibuat dengan `gen_random_uuid()` bawaan PostgreSQL 17.

### Konfigurasi Awal

```sql
-- Ekstensi yang disiapkan oleh migrasi
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";
```

Ekstensi tetap terpasang ketika skema aplikasi di-downgrade agar tidak menghapus ekstensi yang mungkin dipakai komponen lain.

### Tabel Perusahaan

```sql
CREATE TABLE companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    normalized_name VARCHAR(255) NOT NULL UNIQUE,
    display_name VARCHAR(255) NOT NULL,
    industry VARCHAR(100),
    city VARCHAR(100),
    total_jobs_analyzed INT NOT NULL DEFAULT 0,
    age_restricted_jobs_count INT NOT NULL DEFAULT 0,
    age_bias_score NUMERIC(5, 2) NOT NULL DEFAULT 0.00
        CHECK (age_bias_score >= 0 AND age_bias_score <= 100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_companies_normalized_name_trgm
    ON companies USING gin (normalized_name gin_trgm_ops);
```

Keterangan:

- `normalized_name`: Nama perusahaan yang telah dinormalisasi.
- `display_name`: Nama perusahaan yang ditampilkan kepada pengguna.
- `age_bias_score`: Persentase lowongan yang membatasi usia, dengan rentang `0-100`.

### Tabel Lowongan Kerja

```sql
CREATE TABLE job_postings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id) ON DELETE SET NULL,
    job_title VARCHAR(255) NOT NULL,
    job_level VARCHAR(50),
    source_platform VARCHAR(50) NOT NULL,
    source_url TEXT,
    content_hash VARCHAR(64) UNIQUE NOT NULL,
    raw_description TEXT NOT NULL,
    raw_metadata JSONB,
    posted_date DATE,
    scraped_at TIMESTAMPTZ DEFAULT NOW()
);
```

Keterangan:

- `job_level`: Staff, Supervisor, Manager, dan tingkat jabatan lainnya.
- `source_platform`: JobStreet, Glints, LinkedIn, atau laporan pengguna.
- `content_hash`: Hash SHA-256 untuk mencegah duplikasi identik.
- `raw_metadata`: Struktur HTML atau JSON asli yang disimpan sebagai JSONB.

### Tabel Hasil Analisis AI

```sql
CREATE TABLE ai_age_analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_posting_id UUID UNIQUE REFERENCES job_postings(id) ON DELETE CASCADE,
    has_age_restriction BOOLEAN NOT NULL,
    restriction_type VARCHAR(30) NOT NULL
        CHECK (restriction_type IN ('EXPLICIT', 'IMPLICIT', 'NONE')),
    min_age INT,
    max_age INT,
    extracted_evidence TEXT,
    ai_reasoning TEXT,
    confidence_score NUMERIC(4, 3)
        CHECK (confidence_score >= 0 AND confidence_score <= 1),
    model_used VARCHAR(100),
    analyzed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (min_age IS NULL OR max_age IS NULL OR min_age <= max_age)
);
```

Nilai `restriction_type` yang digunakan:

- `EXPLICIT`
- `IMPLICIT`
- `NONE`

### Index Pencarian

```sql
CREATE INDEX ix_companies_display_name_fts
    ON companies
    USING gin (to_tsvector('indonesian', display_name));

CREATE INDEX ix_companies_age_bias_score
    ON companies (age_bias_score DESC);

CREATE INDEX ix_ai_age_analyses_max_age
    ON ai_age_analyses (max_age)
    WHERE max_age IS NOT NULL;
```

## Output Analisis AI

Backend menggunakan Pydantic dan Pydantic JSON schema pada FastAPI agar respons LLM dapat divalidasi sebelum disimpan.

Analisis menggunakan adapter OpenAI-compatible yang dikonfigurasi melalui `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, dan `LLM_TIMEOUT_SECONDS` di `.env`. Hasil wajib konsisten dengan tipe restriksi dan menyertakan bukti untuk klasifikasi restriktif. Konfigurasi yang kosong, respons provider gagal, atau JSON yang tidak valid menghasilkan error eksplisit; sistem tidak menggantinya dengan hasil heuristik.

```json
{
  "has_age_restriction": true,
  "restriction_type": "EXPLICIT",
  "min_age": null,
  "max_age": 28,
  "extracted_evidence": "Kualifikasi: Pria/Wanita, usia maksimal 28 tahun, berpenampilan menarik.",
  "ai_reasoning": "Lowongan secara eksplisit membatasi usia pelamar maksimal 28 tahun meskipun posisi yang dibuka adalah Senior Accounting Staff.",
  "confidence_score": 0.985
}
```

## Endpoint API

Endpoint daftar perusahaan menerima parameter `q`, `industry`, `city`, `page`, dan `page_size` (default 20, maksimum 100). Respons berisi item, nomor halaman, total data, dan jumlah halaman. Detail perusahaan menyertakan riwayat lowongan beserta sumber dan hasil analisis yang tersedia.

`POST /api/v1/submissions/report` menerima `job_title` dan `raw_description`, serta metadata opsional `company_name`, `job_level`, `source_platform`, `source_url`, dan `posted_date`. `source_platform` default ke `user_report`; gambar dan OCR belum didukung. Respons `202 Accepted` berisi ID lowongan, status analisis, dan penanda apakah lowongan baru dibuat. Jika Redis tidak tersedia, endpoint mengembalikan `503` dan menyatakan bahwa laporan sudah tersimpan; kirim ulang laporan yang sama setelah Redis pulih untuk mencoba antrean kembali.

`GET /api/v1/analytics/overview` merangkum seluruh lowongan tersimpan dan hasil analisisnya. `age_bias_rate_pct` adalah persentase lowongan yang terdeteksi membatasi usia dibanding seluruh lowongan yang sudah dianalisis, dibulatkan hingga dua desimal; lowongan pending/failed tidak masuk denominator. Breakdown industri dan level jabatan hanya menghitung lowongan yang sudah dianalisis, dengan kategori `null` untuk data yang tidak diketahui.

| Method | Endpoint | Deskripsi |
| --- | --- | --- |
| `GET` | `/api/v1/companies` | Menampilkan daftar perusahaan berdasarkan skor bias, kota, industri, dan pencarian nama |
| `GET` | `/api/v1/companies/{id}` | Menampilkan detail perusahaan, riwayat lowongan, dan bukti pembatasan usia |
| `GET` | `/api/v1/analytics/overview` | Menampilkan ringkasan lowongan, klasifikasi restriksi, serta breakdown industri dan level jabatan |
| `POST` | `/api/v1/submissions/report` | Menerima laporan teks lowongan dan memasukkan analisis ke antrean |

## Tantangan dan Mitigasi

### Normalisasi Nama Perusahaan

**Masalah**

Nama perusahaan dapat ditulis berbeda-beda di setiap portal.

Contoh:

- PT. Sumber Alfaria Trijaya, Tbk
- Alfamart
- PT Sumber Alfaria Trijaya

**Mitigasi**

- Menghapus prefix dan suffix umum seperti `PT`, `CV`, `Tbk`, dan tanda baca.
- Menggunakan `pg_trgm` untuk mencocokkan nama yang memiliki kemiripan sebelum membuat record baru.

### Poster Lowongan Berbentuk Gambar

**Masalah**

Syarat usia dapat berada di dalam gambar poster pada Instagram atau feed LinkedIn, bukan pada teks caption.

**Mitigasi**

- Menambahkan OCR menggunakan PaddleOCR atau Tesseract.
- Menggunakan multimodal LLM untuk mengekstrak teks dari gambar.
- Memproses hasil ekstraksi melalui pipeline analisis yang sama.

### Legalitas dan Etika Publikasi

**Masalah**

Data perusahaan dapat disalahartikan jika dipublikasikan tanpa konteks atau bukti yang memadai.

**Mitigasi**

- Menampilkan tautan sumber asli.
- Menyertakan tanggal pengambilan data.
- Menampilkan kutipan verbatim dari lowongan.
- Menyajikan data sebagai indeks transparansi berbasis fakta publik, bukan opini subjektif.
