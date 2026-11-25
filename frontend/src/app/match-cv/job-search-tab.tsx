"use client";

import { useState, type FormEvent } from "react";
import type { JobSearchResponse } from "@/lib/api";
import JobSearchResults from "./job-search-results";

function responseDetail(value: unknown): string | null {
  if (
    typeof value === "object" &&
    value !== null &&
    "detail" in value &&
    typeof value.detail === "string"
  ) {
    return value.detail;
  }
  return null;
}

export default function JobSearchTab({
  cvFile,
  disabled = false,
}: {
  cvFile: File | null;
  disabled?: boolean;
}) {
  const [result, setResult] = useState<JobSearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setResult(null);

    if (!cvFile) {
      setError("Pilih file CV di atas terlebih dahulu.");
      return;
    }

    const formData = new FormData(event.currentTarget);
    const location = (formData.get("location") as string) || undefined;
    const job_type = (formData.get("job_type") as string) || undefined;
    const experience_level = (formData.get("experience_level") as string) || undefined;
    const salary_min = formData.get("salary_min")
      ? parseInt(formData.get("salary_min") as string, 10)
      : undefined;
    const salary_max = formData.get("salary_max")
      ? parseInt(formData.get("salary_max") as string, 10)
      : undefined;
    const keywords = (formData.get("keywords") as string) || undefined;

    const uploadData = new FormData();
    uploadData.append("cv_file", cvFile);
    if (location) uploadData.append("location", location);
    if (job_type) uploadData.append("job_type", job_type);
    if (experience_level) uploadData.append("experience_level", experience_level);
    if (salary_min !== undefined) uploadData.append("salary_min", salary_min.toString());
    if (salary_max !== undefined) uploadData.append("salary_max", salary_max.toString());
    if (keywords) uploadData.append("keywords", keywords);

    setIsSubmitting(true);
    try {
      const response = await fetch("/api/v1/cv-matches/search-and-analyze", {
        method: "POST",
        body: uploadData,
      });
      const payload: unknown = await response.json();

      if (!response.ok) {
        const backendDetail = responseDetail(payload);
        let message = "";

        if (response.status === 415 || response.status === 413) {
          message = "Format file tidak valid. Unggah PDF maksimal 8 MB.";
        } else if (response.status === 408) {
          message = "Pencarian memakan waktu lama. Hasil sebagian ditampilkan di bawah.";
          // Still try to show partial results if available
          if (payload && typeof payload === "object" && "results" in payload) {
            setResult(payload as JobSearchResponse);
            if (backendDetail) {
              setError(`Peringatan: ${backendDetail}`);
            }
            setIsSubmitting(false);
            return;
          }
        } else if (response.status === 422) {
          message = "Parameter pencarian tidak valid.";
        } else if (response.status === 500) {
          message = "Terjadi kesalahan di server. Coba lagi.";
        } else if (response.status === 404) {
          message = backendDetail ?? "Backend tidak tersedia atau endpoint tidak ditemukan.";
        } else if (response.status === 503 || response.status === 502) {
          message = "Layanan analisis AI tidak tersedia. Coba lagi nanti.";
        } else {
          message = backendDetail ?? `Pencarian gagal (HTTP ${response.status}). Coba lagi.`;
        }

        setError(message);
        return;
      }

      const searchResult = payload as JobSearchResponse;
      setResult(searchResult);
    } catch (err) {
      // Network error or connection refused
      const errorMsg = err instanceof Error ? err.message : "unknown";
      if (errorMsg.includes("ECONNREFUSED") || errorMsg.includes("Failed to fetch")) {
        setError("Backend tidak tersedia. Pastikan server berjalan dan coba lagi.");
      } else {
        setError("Tidak dapat menghubungi server. Periksa koneksi internet.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <>
      <form
        onSubmit={handleSubmit}
        className="rounded-3xl bg-[#123d33] p-5 text-white shadow-sm sm:p-7"
      >
        <div className="grid gap-5 md:grid-cols-2">
          <div>
            <label htmlFor="location" className="mb-2 block text-sm font-semibold">
              Lokasi (opsional)
            </label>
            <select
              id="location"
              name="location"
              disabled={disabled || isSubmitting}
              className="block w-full rounded-xl border border-white/20 bg-white p-3 text-sm text-slate-900 disabled:opacity-60"
            >
              <option value="">Pilih lokasi...</option>
              <option value="Jakarta">Jakarta</option>
              <option value="Surabaya">Surabaya</option>
              <option value="Bandung">Bandung</option>
              <option value="Yogyakarta">Yogyakarta</option>
              <option value="Bali">Bali</option>
              <option value="Medan">Medan</option>
              <option value="Makassar">Makassar</option>
            </select>
          </div>

          <div>
            <label htmlFor="job_type" className="mb-2 block text-sm font-semibold">
              Tipe Pekerjaan (opsional)
            </label>
            <select
              id="job_type"
              name="job_type"
              disabled={disabled || isSubmitting}
              className="block w-full rounded-xl border border-white/20 bg-white p-3 text-sm text-slate-900 disabled:opacity-60"
            >
              <option value="">Pilih tipe pekerjaan...</option>
              <option value="Full-time">Full-time</option>
              <option value="Remote">Remote</option>
              <option value="Freelance">Freelance</option>
              <option value="Part-time">Part-time</option>
            </select>
          </div>

          <div>
            <label htmlFor="experience_level" className="mb-2 block text-sm font-semibold">
              Level Pengalaman (opsional)
            </label>
            <select
              id="experience_level"
              name="experience_level"
              disabled={disabled || isSubmitting}
              className="block w-full rounded-xl border border-white/20 bg-white p-3 text-sm text-slate-900 disabled:opacity-60"
            >
              <option value="">Pilih level pengalaman...</option>
              <option value="Entry Level">Entry Level</option>
              <option value="Mid Level">Mid Level</option>
              <option value="Senior Level">Senior Level</option>
            </select>
          </div>

          <div>
            <label htmlFor="keywords" className="mb-2 block text-sm font-semibold">
              Kata Kunci Lowongan (opsional)
            </label>
            <input
              id="keywords"
              name="keywords"
              type="text"
              placeholder="cth: React, Node.js, Python"
              disabled={disabled || isSubmitting}
              className="block w-full rounded-xl border border-white/20 bg-white p-3 text-sm text-slate-900 placeholder-slate-400 disabled:opacity-60"
            />
          </div>

          <div>
            <label htmlFor="salary_min" className="mb-2 block text-sm font-semibold">
              Gaji Minimum (opsional)
            </label>
            <input
              id="salary_min"
              name="salary_min"
              type="number"
              placeholder="cth: 5000000"
              disabled={disabled || isSubmitting}
              className="block w-full rounded-xl border border-white/20 bg-white p-3 text-sm text-slate-900 placeholder-slate-400 disabled:opacity-60"
            />
          </div>

          <div>
            <label htmlFor="salary_max" className="mb-2 block text-sm font-semibold">
              Gaji Maksimum (opsional)
            </label>
            <input
              id="salary_max"
              name="salary_max"
              type="number"
              placeholder="cth: 15000000"
              disabled={disabled || isSubmitting}
              className="block w-full rounded-xl border border-white/20 bg-white p-3 text-sm text-slate-900 placeholder-slate-400 disabled:opacity-60"
            />
          </div>
        </div>

        <p className="mt-4 text-sm leading-6 text-emerald-50/90">
          Cari lowongan dari Indeed, LinkedIn, dan remote.io. Filter bersifat opsional dan dapat
          diubah sesuai preferensi Anda.
        </p>

        {error && (
          <p role="alert" className="mt-4 rounded-xl bg-rose-100 p-3 text-sm text-rose-900">
            {error}
          </p>
        )}

        {!cvFile && (
          <p role="alert" className="mt-4 rounded-xl bg-amber-100 p-3 text-sm text-amber-900">
            Pilih file CV di atas terlebih dahulu.
          </p>
        )}

        <button
          type="submit"
          disabled={disabled || isSubmitting || !cvFile}
          className="mt-5 rounded-xl bg-[#c4f06b] px-5 py-3 text-sm font-semibold text-slate-900 transition hover:bg-[#d3fa87] disabled:cursor-wait disabled:opacity-70"
        >
          {isSubmitting ? "Mencari lowongan dari Indeed, LinkedIn, dan remote.io..." : "Cari & Analisis dari Berbagai Sumber"}
        </button>
      </form>

      {result && (
        <JobSearchResults
          results={result.results}
          cvSkills={result.cv_skills}
          searchDurationMs={result.search_duration_ms}
          warnings={result.warnings || []}
        />
      )}
    </>
  );
}
