"use client";

import { useState, type FormEvent } from "react";

import type { CvJobAiAssessment, CvMatchResponse } from "@/lib/api";

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

function CvResults({
  result,
  cvFiles,
}: {
  result: CvMatchResponse;
  cvFiles: Record<"CV 1" | "CV 2", File | null>;
}) {
  const [assessments, setAssessments] = useState<Record<string, CvJobAiAssessment>>({});
  const [loadingJobs, setLoadingJobs] = useState<string[]>([]);
  const [assessmentErrors, setAssessmentErrors] = useState<Record<string, string>>({});

  async function loadAssessment(cvFile: File | null, jobId: string) {
    if (!cvFile || !jobId) {
      setAssessmentErrors((current) => ({
        ...current,
        [jobId || "cv"]: "File CV atau ID lowongan tidak tersedia. Unggah ulang CV lalu coba kembali.",
      }));
      return;
    }
    setLoadingJobs((current) => [...current, jobId]);
    setAssessmentErrors((current) => ({ ...current, [jobId]: "" }));
    try {
      const response = await fetch("/api/v1/cv-matches/assess-job", {
        method: "POST",
        body: (() => {
          const data = new FormData();
          data.append("cv_file", cvFile);
          data.append("job_posting_id", jobId);
          return data;
        })(),
      });
      const payload: unknown = await response.json();
      if (!response.ok) {
        const backendDetail = responseDetail(payload);
        let message = "";
        
        if (response.status === 404) {
          message = "Lowongan ini tidak ditemukan di database kami. CV Anda berhasil dibaca, namun analisis tidak dapat dilakukan karena data lowongan tidak tersedia.";
        } else if (response.status === 503 || response.status === 502) {
          message = "Layanan analisis AI sementara tidak tersedia. CV Anda berhasil diterima — coba lagi dalam beberapa saat.";
        } else if (response.status === 415 || response.status === 413) {
          message = backendDetail ?? `Analisis AI gagal (HTTP ${response.status}). CV Anda berhasil diunggah — coba lagi.`;
        } else {
          message = `Analisis AI gagal (HTTP ${response.status}). CV Anda berhasil diunggah — coba lagi.`;
        }
        
        const finalMessage = backendDetail && backendDetail !== message 
          ? `${message} (${backendDetail})` 
          : message;
        
        setAssessmentErrors((current) => ({
          ...current,
          [jobId]: finalMessage,
        }));
        return;
      }
      setAssessments((current) => ({ ...current, [jobId]: payload as CvJobAiAssessment }));
    } catch {
      setAssessmentErrors((current) => ({ ...current, [jobId]: "Tidak dapat menghubungi layanan AI. CV Anda sudah diproses di browser — pastikan koneksi internet aktif dan coba lagi." }));
    } finally {
      setLoadingJobs((current) => current.filter((id) => id !== jobId));
    }
  }

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
                      {formatPercentage(company.match_percentage)} skill cocok
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
                          {assessments[job.job_posting_id] ? (
                            <div className="mt-3 rounded-xl bg-sky-50 p-4 text-sm text-slate-700">
                              <p className="font-semibold text-slate-900">
                                Analisis AI · {assessments[job.job_posting_id].fit_level === "strong" ? "Kuat" : assessments[job.job_posting_id].fit_level === "moderate" ? "Sedang" : "Rendah"}
                              </p>
                              <p className="mt-1">{assessments[job.job_posting_id].summary}</p>
                              <p className="mt-2"><strong>Kekuatan:</strong> {assessments[job.job_posting_id].strengths.join("; ") || "Belum teridentifikasi"}</p>
                              <p className="mt-1"><strong>Yang perlu dicek:</strong> {assessments[job.job_posting_id].gaps.join("; ") || "Tidak ada gap eksplisit terdeteksi"}</p>
                              <p className="mt-2 text-xs">{assessments[job.job_posting_id].caveat}</p>
                            </div>
                          ) : (
                            <>
                              <button
                                type="button"
                                disabled={loadingJobs.includes(job.job_posting_id)}
                                onClick={() => void loadAssessment(cvFiles[profile.label], job.job_posting_id)}
                                className="mt-3 rounded-lg border border-sky-800 px-3 py-2 text-sm font-medium text-sky-900 disabled:opacity-60"
                              >
                                {loadingJobs.includes(job.job_posting_id) ? "Menganalisis…" : "Analisis AI lebih detail"}
                              </button>
                              {assessmentErrors[job.job_posting_id] && (
                                <p role="alert" className="mt-2 text-sm text-rose-700">{assessmentErrors[job.job_posting_id]}</p>
                              )}
                            </>
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
  const [cvFiles, setCvFiles] = useState<Record<"CV 1" | "CV 2", File | null>>({ "CV 1": null, "CV 2": null });

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setResult(null);

    const formData = new FormData(event.currentTarget);
    const cvA = formData.get("cv_a");
    const cvB = formData.get("cv_b");
    if (!(cvA instanceof File) || cvA.size === 0) {
      setError("Pilih file CV pertama sebelum memulai pencocokan.");
      return;
    }
    if (!cvA.name.toLowerCase().endsWith(".pdf")) {
      setError("File CV pertama harus berformat PDF.");
      return;
    }
    if (cvA.size > MAX_FILE_BYTES) {
      setError("Ukuran setiap file CV maksimal 8 MB.");
      return;
    }
    if (cvB instanceof File && cvB.size > 0) {
      if (!cvB.name.toLowerCase().endsWith(".pdf")) {
        setError("File CV kedua harus berformat PDF.");
        return;
      }
      if (cvB.size > MAX_FILE_BYTES) {
        setError("Ukuran setiap file CV maksimal 8 MB.");
        return;
      }
    }

    const uploadData = new FormData();
    uploadData.append("cv_a", cvA);
    if (cvB instanceof File && cvB.size > 0) {
      uploadData.append("cv_b", cvB);
    }
    setIsSubmitting(true);
    try {
      const response = await fetch("/api/cv-matches", {
        method: "POST",
        body: uploadData,
      });
      const payload: unknown = await response.json();
      if (!response.ok) {
        setError(responseDetail(payload) ?? "Pencocokan CV tidak berhasil. Coba lagi.");
        return;
      }
      const matchResult = payload as CvMatchResponse;
      setCvFiles({
        "CV 1": cvA,
        "CV 2": cvB instanceof File && cvB.size > 0 ? cvB : null,
      });
      setResult(matchResult);
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
            { name: "cv_a", label: "CV pertama (wajib)", required: true },
            { name: "cv_b", label: "CV kedua (opsional)", required: false },
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
                required={field.required}
                className="block w-full rounded-xl border border-white/20 bg-white p-3 text-sm text-slate-900 file:mr-3 file:rounded-lg file:border-0 file:bg-emerald-100 file:px-3 file:py-2 file:text-sm file:font-semibold file:text-emerald-900"
              />
            </div>
          ))}
        </div>
        <p className="mt-4 text-sm leading-6 text-emerald-50/90">
          Unggah CV pertama; CV kedua opsional. PDF harus berisi teks yang dapat dipilih, maksimal
          8 MB dan 30 halaman per file. PDF hasil scan belum didukung.
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
      {result && <CvResults result={result} cvFiles={cvFiles} />}
    </>
  );
}
