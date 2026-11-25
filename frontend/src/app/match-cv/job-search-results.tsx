"use client";

import type { JobSearchResult } from "@/lib/api";

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

function getMatchBadgeColor(percentage: number): {
  bg: string;
  text: string;
} {
  if (percentage <= 33) return { bg: "bg-rose-100", text: "text-rose-800" };
  if (percentage <= 66) return { bg: "bg-amber-100", text: "text-amber-800" };
  return { bg: "bg-emerald-100", text: "text-emerald-800" };
}

export default function JobSearchResults({
  results,
  cvSkills,
  searchDurationMs,
  warnings,
}: {
  results: JobSearchResult[];
  cvSkills: string[];
  searchDurationMs: number;
  warnings: string[];
}) {
  const searchDurationSec = (searchDurationMs / 1000).toFixed(1);

  return (
    <section aria-live="polite" className="mt-10 space-y-8">
      {/* CV Skills */}
      <section className="rounded-3xl border border-slate-200 bg-white p-5 sm:p-7">
        <p className="text-sm font-semibold">Keterampilan yang dikenali dari CV</p>
        {cvSkills.length > 0 ? (
          <ul className="mt-2 flex flex-wrap gap-2">
            {cvSkills.map((skill) => (
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
      </section>

      {/* Search Metadata & Warnings */}
      <div className="space-y-4">
        <section className="rounded-2xl border border-slate-200 bg-white p-5">
          <p className="text-sm text-slate-600">
            Menemukan <span className="font-semibold text-slate-900">{results.length} lowongan</span> dalam{" "}
            <span className="font-semibold text-slate-900">{searchDurationSec}s</span>
          </p>
        </section>

        {warnings.length > 0 && (
          <section role="alert" className="rounded-2xl border border-amber-200 bg-amber-50 p-5">
            <p className="text-sm font-semibold text-amber-900">Peringatan</p>
            <ul className="mt-2 space-y-1">
              {warnings.map((warning, idx) => (
                <li key={idx} className="text-sm text-amber-800">
                  • {warning}
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>

      {/* Results Grid */}
      {results.length > 0 ? (
        <ol className="space-y-6">
          {results.map((result, index) => {
            const sourceUrl = safeSourceUrl(result.source_url);
            const matchColor = getMatchBadgeColor(result.keyword_match_percentage);

            return (
              <li
                key={`${result.company_name}-${result.job_title}-${index}`}
                className="rounded-2xl border border-slate-200 bg-white p-5"
              >
                {/* Header */}
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h3 className="text-lg font-semibold">{result.job_title}</h3>
                    <p className="mt-1 text-sm text-slate-600">{result.company_name}</p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">
                      {result.source_platform}
                    </span>
                    <span className={`rounded-full ${matchColor.bg} ${matchColor.text} px-3 py-1 text-xs font-semibold`}>
                      {formatPercentage(result.keyword_match_percentage)} cocok
                    </span>
                  </div>
                </div>

                {/* Matched Skills */}
                {result.matched_skills.length > 0 && (
                  <div className="mt-3">
                    <p className="text-xs font-medium text-slate-600">Keterampilan yang cocok</p>
                    <ul className="mt-1 flex flex-wrap gap-1.5">
                      {result.matched_skills.map((skill) => (
                        <li
                          key={skill}
                          className="rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-900"
                        >
                          {skill}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* AI Assessment */}
                {result.ai_assessment ? (
                  <div className="mt-4 rounded-xl bg-sky-50 p-4 text-sm text-slate-700">
                    <p className="font-semibold text-slate-900">
                      Analisis AI ·{" "}
                      {result.ai_assessment.fit_level === "strong"
                        ? "Kuat"
                        : result.ai_assessment.fit_level === "moderate"
                          ? "Sedang"
                          : "Rendah"}
                    </p>
                    <p className="mt-1">{result.ai_assessment.summary}</p>
                    <p className="mt-2">
                      <strong>Kekuatan:</strong>{" "}
                      {result.ai_assessment.strengths.join("; ") || "Belum teridentifikasi"}
                    </p>
                    <p className="mt-1">
                      <strong>Yang perlu dicek:</strong>{" "}
                      {result.ai_assessment.gaps.join("; ") || "Tidak ada gap eksplisit terdeteksi"}
                    </p>
                    <p className="mt-2 text-xs">{result.ai_assessment.caveat}</p>
                  </div>
                ) : result.analysis_status === "timeout" ? (
                  <div className="mt-4 rounded-xl bg-sky-50 p-4 text-sm text-slate-700">
                    <p className="font-semibold text-slate-900">Analisis AI</p>
                    <p className="mt-1">Analisis AI sedang diproses...</p>
                  </div>
                ) : result.analysis_status === "error" ? (
                  <div className="mt-4 rounded-xl bg-sky-50 p-4 text-sm text-slate-700">
                    <p className="font-semibold text-slate-900">Analisis AI</p>
                    <p className="mt-1">Analisis AI tidak tersedia</p>
                  </div>
                ) : null}

                {/* Result Warnings */}
                {result.warnings.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {result.warnings.map((warning, idx) => (
                      <span key={idx} className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-800">
                        {warning}
                      </span>
                    ))}
                  </div>
                )}

                {/* Source Link */}
                {sourceUrl && (
                  <a
                    href={sourceUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-4 inline-block text-sm font-medium text-emerald-800 underline underline-offset-4"
                  >
                    Buka Lowongan →
                  </a>
                )}
              </li>
            );
          })}
        </ol>
      ) : (
        <section className="rounded-2xl border border-slate-200 bg-slate-50 p-5 text-center">
          <p className="text-sm text-slate-600">
            Tidak ada lowongan yang cocok dengan kriteria pencarian Anda. Coba ubah filter.
          </p>
        </section>
      )}
    </section>
  );
}
