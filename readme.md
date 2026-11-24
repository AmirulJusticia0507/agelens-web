# Agelens Web

> Dokumentasi rancangan sistem untuk mendeteksi pembatasan usia pada lowongan kerja di Indonesia.

## Daftar Isi

- [Latar Belakang](#latar-belakang)
- [Tujuan Sistem](#tujuan-sistem)
- [Scope MVP dan Keputusan Teknis](#scope-mvp-dan-keputusan-teknis)
- [Tech Stack](#tech-stack)
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
- **pgvector** untuk pencarian kemiripan dan deteksi duplikasi semantik.
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

### Konfigurasi Awal

```sql
-- Aktifkan ekstensi UUID dan pgvector
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
```

### Tabel Perusahaan

```sql
CREATE TABLE companies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    normalized_name VARCHAR(255) NOT NULL UNIQUE,
    display_name VARCHAR(255) NOT NULL,
    industry VARCHAR(100),
    city VARCHAR(100),
    total_jobs_analyzed INT DEFAULT 0,
    age_restricted_jobs_count INT DEFAULT 0,
    age_bias_score NUMERIC(5, 2) DEFAULT 0.00,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

Keterangan:

- `normalized_name`: Nama perusahaan yang telah dinormalisasi.
- `display_name`: Nama perusahaan yang ditampilkan kepada pengguna.
- `age_bias_score`: Persentase lowongan yang membatasi usia, dengan rentang `0-100`.

### Tabel Lowongan Kerja

```sql
CREATE TABLE job_postings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
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
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_posting_id UUID UNIQUE REFERENCES job_postings(id) ON DELETE CASCADE,
    has_age_restriction BOOLEAN NOT NULL,
    restriction_type VARCHAR(30) NOT NULL,
    min_age INT,
    max_age INT,
    extracted_evidence TEXT,
    ai_reasoning TEXT,
    confidence_score NUMERIC(4, 3),
    model_used VARCHAR(100),
    analyzed_at TIMESTAMPTZ DEFAULT NOW()
);
```

Nilai `restriction_type` yang digunakan:

- `EXPLICIT`
- `IMPLICIT`
- `NONE`

### Index Pencarian

```sql
CREATE INDEX idx_companies_name
    ON companies
    USING gin (to_tsvector('indonesian', display_name));

CREATE INDEX idx_companies_bias_score
    ON companies (age_bias_score DESC);

CREATE INDEX idx_analyses_max_age
    ON ai_age_analyses (max_age)
    WHERE max_age IS NOT NULL;
```

## Output Analisis AI

Backend menggunakan Pydantic dan Pydantic JSON schema pada FastAPI agar respons LLM dapat divalidasi sebelum disimpan.

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

| Method | Endpoint | Deskripsi |
| --- | --- | --- |
| `GET` | `/api/v1/companies` | Menampilkan daftar perusahaan berdasarkan skor bias, kota, industri, dan pencarian nama |
| `GET` | `/api/v1/companies/{id}` | Menampilkan detail perusahaan, riwayat lowongan, dan bukti pembatasan usia |
| `GET` | `/api/v1/analytics/overview` | Menampilkan statistik industri, jabatan, dan rata-rata batas usia |
| `POST` | `/api/v1/submissions/report` | Menerima teks atau screenshot lowongan untuk diproses OCR dan dikirim ke antrean analisis |

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
