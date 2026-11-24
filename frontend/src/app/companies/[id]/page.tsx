import Link from "next/link";
import { notFound } from "next/navigation";

import { fetchApi, type CompanyDetail, type JobPosting } from "@/lib/api";

export const instant = false;

const restrictionLabels = {
  EXPLICIT: "Batas usia eksplisit",
  IMPLICIT: "Indikasi implisit",
  NONE: "Tidak ditemukan indikasi",
} as const;

const restrictionStyles = {
  EXPLICIT: "bg-rose-100 text-rose-800",
  IMPLICIT: "bg-amber-100 text-amber-900",
  NONE: "bg-emerald-100 text-emerald-800",
} as const;

const statusLabels = {
  pending: "Menunggu analisis",
  processing: "Sedang dianalisis",
  completed: "Analisis selesai",
  failed: "Analisis gagal",
} as const;

function sourceLink(value: string | null): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:" ? url.toString() : null;
  } catch {
    return null;
  }
}

function formatDate(value: string | null, includeTime = false): string {
  if (!value) return "Tanggal tidak tersedia";
  const date = new Date(includeTime ? value : `${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return "Tanggal tidak tersedia";
  return new Intl.DateTimeFormat("id-ID", {
    dateStyle: "medium",
    ...(includeTime ? { timeStyle: "short" as const } : {}),
  }).format(date);
}

function JobCard({ job }: { job: JobPosting }) {
  const href = sourceLink(job.source_url);
  const analysis = job.analysis;

  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-7">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
            {job.source_platform.replaceAll("_", " ")}
            {job.job_level ? ` · ${job.job_level}` : ""}
          </p>
          <h3 className="mt-2 text-xl font-semibold tracking-tight">{job.job_title}</h3>
          <p className="mt-2 text-sm text-slate-500">
            Dipublikasikan {formatDate(job.posted_date)} · Dicatat{" "}
            {formatDate(job.scraped_at, true)}
          </p>
        </div>
        {analysis ? (
          <span
            className={`w-fit rounded-full px-3 py-1.5 text-xs font-semibold ${restrictionStyles[analysis.restriction_type]}`}
          >
            {restrictionLabels[analysis.restriction_type]}
          </span>
        ) : (
          <span className="w-fit rounded-full bg-slate-100 px-3 py-1.5 text-xs font-semibold text-slate-700">
            {statusLabels[job.analysis_status]}
          </span>
        )}
      </div>

      {analysis ? (
        <div className="mt-6 grid gap-5 border-t border-slate-100 pt-5 md:grid-cols-[1fr_auto]">
          <div>
            <p className="text-sm font-semibold">Bukti dari lowongan</p>
            {analysis.extracted_evidence ? (
              <blockquote className="mt-3 border-l-2 border-emerald-600 pl-4 text-sm leading-6 text-slate-700">
                “{analysis.extracted_evidence}”
              </blockquote>
            ) : (
              <p className="mt-2 text-sm text-slate-500">Tidak ada kutipan bukti yang disimpan.</p>
            )}
            {analysis.ai_reasoning && (
              <p className="mt-4 text-sm leading-6 text-slate-600">{analysis.ai_reasoning}</p>
            )}
          </div>
          <dl className="grid grid-cols-2 gap-4 text-sm md:min-w-48 md:grid-cols-1">
            <div>
              <dt className="text-slate-500">Rentang usia</dt>
              <dd className="mt-1 font-medium">
                {analysis.min_age ?? "—"} – {analysis.max_age ?? "—"}
              </dd>
            </div>
            <div>
              <dt className="text-slate-500">Confidence</dt>
              <dd className="mt-1 font-medium">
                {analysis.confidence_score == null
                  ? "—"
                  : `${Math.round(analysis.confidence_score * 100)}%`}
              </dd>
            </div>
          </dl>
        </div>
      ) : (
        <p className="mt-5 border-t border-slate-100 pt-4 text-sm text-slate-600">
          {job.analysis_status === "failed"
            ? "Analisis belum berhasil. Bukti pembatasan usia belum tersedia."
            : "Bukti dan klasifikasi akan tersedia setelah analisis selesai."}
        </p>
      )}

      <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4 text-sm">
        <span className="text-slate-500">
          {analysis?.model_used ? `Dianalisis dengan ${analysis.model_used}` : "Sumber laporan"}
        </span>
        {href && (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="font-medium text-emerald-800 underline decoration-emerald-300 underline-offset-4 hover:text-emerald-950"
          >
            Buka sumber asli
          </a>
        )}
      </div>
      <details className="mt-4 text-sm">
        <summary className="cursor-pointer font-medium text-slate-600">
          Lihat teks lowongan
        </summary>
        <p className="mt-3 whitespace-pre-wrap leading-6 text-slate-600">{job.raw_description}</p>
      </details>
    </article>
  );
}

export default async function CompanyDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const result = await fetchApi<CompanyDetail>(`companies/${encodeURIComponent(id)}`);

  if ("error" in result) {
    if (result.status === 404 || result.status === 422) notFound();
    return (
      <main className="min-h-screen bg-[#f5f7f5] px-5 py-12 text-slate-900 sm:px-8">
        <div role="alert" className="mx-auto max-w-3xl rounded-2xl bg-rose-50 p-6 text-rose-900">
          <h1 className="font-semibold">Profil perusahaan belum dapat dimuat</h1>
          <p className="mt-2 text-sm">{result.error}</p>
          <Link className="mt-5 inline-block text-sm font-medium underline" href="/">
            Kembali ke pencarian
          </Link>
        </div>
      </main>
    );
  }

  const company = result.data;
  const score =
    company.total_jobs_analyzed > 0
      ? `${new Intl.NumberFormat("id-ID", { maximumFractionDigits: 1 }).format(company.age_bias_score)}%`
      : "Belum tersedia";

  return (
    <div className="min-h-screen bg-[#f5f7f5] text-slate-900">
      <header className="border-b border-slate-200/80 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-5 py-4 sm:px-8">
          <Link href="/" className="font-semibold tracking-tight">
            ← Kembali ke perusahaan
          </Link>
          <Link href="/analytics" className="text-sm text-slate-600 hover:text-emerald-800">
            Analitik
          </Link>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-5 pb-16 sm:px-8">
        <section className="py-10 sm:py-14">
          <p className="text-sm font-medium text-emerald-800">Profil perusahaan</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">
            {company.display_name}
          </h1>
          <p className="mt-3 text-slate-600">
            {[company.industry, company.city].filter(Boolean).join(" · ") ||
              "Informasi industri dan lokasi belum tersedia"}
          </p>
          <div className="mt-8 grid gap-3 sm:grid-cols-3">
            <div className="rounded-2xl border border-slate-200 bg-white p-5">
              <p className="text-sm text-slate-500">Skor indikasi age-bias</p>
              <p className="mt-2 text-2xl font-semibold">{score}</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white p-5">
              <p className="text-sm text-slate-500">Lowongan dianalisis</p>
              <p className="mt-2 text-2xl font-semibold">
                {new Intl.NumberFormat("id-ID").format(company.total_jobs_analyzed)}
              </p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white p-5">
              <p className="text-sm text-slate-500">Ada indikasi pembatasan usia</p>
              <p className="mt-2 text-2xl font-semibold">
                {new Intl.NumberFormat("id-ID").format(company.age_restricted_jobs_count)}
              </p>
            </div>
          </div>
        </section>

        <section aria-labelledby="job-list-title">
          <div className="mb-5 flex items-end justify-between gap-4">
            <div>
              <p className="text-sm font-medium text-emerald-800">Riwayat dan bukti</p>
              <h2 id="job-list-title" className="mt-1 text-2xl font-semibold tracking-tight">
                Lowongan kerja
              </h2>
            </div>
            <p className="text-sm text-slate-500">{company.job_postings.length} lowongan</p>
          </div>
          {company.job_postings.length > 0 ? (
            <div className="space-y-4">
              {company.job_postings.map((job) => (
                <JobCard key={job.id} job={job} />
              ))}
            </div>
          ) : (
            <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-600">
              Belum ada lowongan yang dapat ditampilkan untuk perusahaan ini.
            </div>
          )}
        </section>

        <p className="mt-8 text-xs leading-5 text-slate-500">
          Analisis merangkum teks lowongan yang tercatat dan bukan penilaian hukum atau kesimpulan
          tentang seluruh praktik perusahaan.
        </p>
      </main>
    </div>
  );
}
