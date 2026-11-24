"use client";

import { useState, type FormEvent } from "react";

import type { CvMatchResponse } from "@/lib/api";

const MAX_FILE_BYTES = 8 * 1024 * 1024;

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

function safeSourceUrl(value: string | null): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:" ? url.toString() : null;
  } catch {
    return null;
  }
}

function formatPercentage(value: number): string {
  return `${new Intl.NumberFormat("id-ID", { maximumFractionDigits: 1 }).format(value)}%`;
}

function CvResults({ result }: { result: CvMatchResponse }) {
  return (
    <section aria-live="polite" className="mt-10 space-y-8">
      {result.profiles.map((profile) => (
        <section
          key={profile.label}
          aria-labelledby={`${profile.label.replace(" ", "-")}-title`}
          className="rounded-3xl border border-slate-200 bg-white p-5 sm:p-7"
        >
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-sm font-medium text-emerald-800">{profile.label}</p>
              <h2
                id={`${profile.label.replace(" ", "-")}-title`}
                className="mt-1 text-2xl font-semibold tracking-tight"
              >
                Perusahaan yang cocok
              </h2>
            </div>
            <p className="text-sm text-slate-500">
              {profile.jobs_considered} lowongan dibandingkan
            </p>
          </div>

          <div className="mt-5">
            <p className="text-sm font-semibold">Keterampilan yang dikenali</p>
            {profile.skills.length > 0 ? (
              <ul className="mt-2 flex flex-wrap gap-2">
                {profile.skills.map((skill) => (
                  <li
                    key={skill}
                    className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-900"
                  >
                    {skill}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-sm text-slate-600">
                Belum ada keterampilan teknis yang dikenali dari teks CV.
              </p>
            )}
          </div>

          {profile.companies.length > 0 ? (
            <ol className="mt-6 space-y-4">
              {profile.companies.map((company, index) => (
                <li
                  key={company.company_id}
                  className="rounded-2xl border border-slate-200 p-5"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                        Peringkat {index + 1}
                      </p>
                      <h3 className="mt-1 text-lg font-semibold">{company.display_name}</h3>
                    </div>
                    <span className="rounded-full bg-emerald-50 px-3 py-1.5 text-sm font-semibold text-emerald-900">
                      {formatPercentage(company.match_percentage)} cocok
                    </span>
                  </div>
                  <p className="mt-3 text-sm text-slate-600">
                    Keterampilan yang cocok: {company.matched_skills.join(", ")}
                  </p>
                  <ul className="mt-4 divide-y divide-slate-100">
                    {company.jobs.map((job) => {
                      const sourceUrl = safeSourceUrl(job.source_url);
                      return (
                        <li key={job.job_posting_id} className="py-4 first:pt-0 last:pb-0">
                          <div className="flex flex-wrap items-baseline justify-between gap-2">
                            <h4 className="font-medium">{job.job_title}</h4>
                            <span className="text-sm text-slate-500">
                              {formatPercentage(job.match_percentage)}
                            </span>
                          </div>
                          <p className="mt-1 text-sm text-slate-600">
                            {job.source_platform.replaceAll("_", " ")} · Cocok:{" "}
                            {job.matched_skills.join(", ")}
                          </p>
                          {job.summary_only && (
                            <p className="mt-2 text-xs leading-5 text-amber-800">
                              Data lowongan ini berupa ringkasan; verifikasi kecocokan pada sumber
                              asli.
                            </p>
                          )}
                          {sourceUrl && (
                            <a
                              href={sourceUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="mt-2 inline-block text-sm font-medium text-emerald-800 underline underline-offset-4"
                            >
                              Buka sumber lowongan
                            </a>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                </li>
              ))}
            </ol>
          ) : (
            <p className="mt-6 rounded-xl bg-slate-50 p-4 text-sm text-slate-600">
              Belum ada lowongan tersimpan yang cocok dengan keterampilan yang dikenali dari CV
              ini.
            </p>
          )}
        </section>
      ))}
      <p className="text-xs leading-5 text-slate-500">
        Persentase adalah kecocokan kata kunci keterampilan yang dikenali, bukan jaminan lolos
        seleksi. Hasil hanya membandingkan lowongan yang tersimpan di AgeLens.
      </p>
    </section>
  );
}

export default function CvMatchForm() {
  const [result, setResult] = useState<CvMatchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setResult(null);

    const formData = new FormData(event.currentTarget);
    for (const fieldName of ["cv_a", "cv_b"]) {
      const file = formData.get(fieldName);
      if (!(file instanceof File) || file.size === 0) {
        setError("Pilih kedua file CV sebelum memulai pencocokan.");
        return;
      }
      if (!file.name.toLowerCase().endsWith(".pdf")) {
        setError("Kedua file harus berformat PDF.");
        return;
      }
      if (file.size > MAX_FILE_BYTES) {
        setError("Ukuran setiap file CV maksimal 8 MB.");
        return;
      }
    }

    setIsSubmitting(true);
    try {
      const response = await fetch("/api/cv-matches", {
        method: "POST",
        body: formData,
      });
      const payload: unknown = await response.json();
      if (!response.ok) {
        setError(responseDetail(payload) ?? "Pencocokan CV tidak berhasil. Coba lagi.");
        return;
      }
      setResult(payload as CvMatchResponse);
    } catch {
      setError("Tidak dapat menghubungi layanan pencocokan. Coba lagi.");
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
          {[
            { name: "cv_a", label: "CV pertama" },
            { name: "cv_b", label: "CV kedua" },
          ].map((field) => (
            <div key={field.name}>
              <label htmlFor={field.name} className="mb-2 block text-sm font-semibold">
                {field.label}
              </label>
              <input
                id={field.name}
                name={field.name}
                type="file"
                accept="application/pdf,.pdf"
                required
                className="block w-full rounded-xl border border-white/20 bg-white p-3 text-sm text-slate-900 file:mr-3 file:rounded-lg file:border-0 file:bg-emerald-100 file:px-3 file:py-2 file:text-sm file:font-semibold file:text-emerald-900"
              />
            </div>
          ))}
        </div>
        <p className="mt-4 text-sm leading-6 text-emerald-50/90">
          PDF harus berisi teks yang dapat dipilih, maksimal 8 MB dan 30 halaman per file. PDF
          hasil scan belum didukung.
        </p>
        {error && (
          <p role="alert" className="mt-4 rounded-xl bg-rose-100 p-3 text-sm text-rose-900">
            {error}
          </p>
        )}
        <button
          type="submit"
          disabled={isSubmitting}
          className="mt-5 rounded-xl bg-[#c4f06b] px-5 py-3 text-sm font-semibold text-slate-900 transition hover:bg-[#d3fa87] disabled:cursor-wait disabled:opacity-70"
        >
          {isSubmitting ? "Menganalisis CV..." : "Bandingkan kecocokan"}
        </button>
      </form>
      {result && <CvResults result={result} />}
    </>
  );
}
