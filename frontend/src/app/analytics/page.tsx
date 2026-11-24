import Link from "next/link";

import { fetchApi, type AnalyticsOverview, type CategoryAnalytics } from "@/lib/api";

export const instant = false;

const restrictionLabels = {
  EXPLICIT: "Eksplisit",
  IMPLICIT: "Implisit",
  NONE: "Netral",
} as const;

function formatNumber(value: number): string {
  return new Intl.NumberFormat("id-ID").format(value);
}

function formatRate(value: number): string {
  return `${new Intl.NumberFormat("id-ID", {
    maximumFractionDigits: 2,
    minimumFractionDigits: 2,
  }).format(value)}%`;
}

function BreakdownTable({
  title,
  rows,
}: {
  title: string;
  rows: CategoryAnalytics[];
}) {
  return (
    <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
      <div className="border-b border-slate-100 px-5 py-4">
        <h2 className="font-semibold">{title}</h2>
      </div>
      {rows.length === 0 ? (
        <p className="px-5 py-8 text-sm text-slate-500">Belum ada data analisis untuk diringkas.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th scope="col" className="px-5 py-3 font-medium">
                  Kategori
                </th>
                <th scope="col" className="px-5 py-3 text-right font-medium">
                  Dianalisis
                </th>
                <th scope="col" className="px-5 py-3 text-right font-medium">
                  Terindikasi
                </th>
                <th scope="col" className="px-5 py-3 text-right font-medium">
                  Persentase
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((row) => (
                <tr key={row.category ?? "unknown"}>
                  <th scope="row" className="px-5 py-3.5 font-medium text-slate-800">
                    {row.category || "Tidak diketahui"}
                  </th>
                  <td className="px-5 py-3.5 text-right text-slate-600">
                    {formatNumber(row.analyzed_jobs)}
                  </td>
                  <td className="px-5 py-3.5 text-right text-slate-600">
                    {formatNumber(row.restricted_jobs)}
                  </td>
                  <td className="px-5 py-3.5 text-right font-medium text-slate-800">
                    {formatRate(row.age_bias_rate_pct)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export default async function AnalyticsPage() {
  const result = await fetchApi<AnalyticsOverview>("analytics/overview");
  if ("error" in result) {
    return (
      <main className="min-h-screen bg-[#f5f7f5] px-5 py-12 text-slate-900 sm:px-8">
        <div role="alert" className="mx-auto max-w-4xl rounded-2xl bg-rose-50 p-6 text-rose-900">
          <h1 className="font-semibold">Analitik belum dapat dimuat</h1>
          <p className="mt-2 text-sm">{result.error}</p>
          <Link className="mt-5 inline-block text-sm font-medium underline" href="/">
            Kembali ke pencarian
          </Link>
        </div>
      </main>
    );
  }

  const overview = result.data;
  const metrics = [
    { label: "Perusahaan", value: formatNumber(overview.total_companies) },
    { label: "Lowongan tersimpan", value: formatNumber(overview.total_submissions) },
    { label: "Sudah dianalisis", value: formatNumber(overview.analyzed_jobs) },
    { label: "Ada indikasi restriksi", value: formatNumber(overview.restricted_jobs) },
  ];

  return (
    <div className="min-h-screen bg-[#f5f7f5] text-slate-900">
      <header className="border-b border-slate-200/80 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-4 sm:px-8">
          <Link href="/" className="font-semibold tracking-tight">
            ← Agelens
          </Link>
          <Link href="/" className="text-sm text-slate-600 hover:text-emerald-800">
            Cari perusahaan
          </Link>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-5 pb-16 sm:px-8">
        <section className="py-10 sm:py-14">
          <p className="text-sm font-medium text-emerald-800">Ringkasan data</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">
            Analitik lowongan kerja
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600">
            Ringkasan ini dihitung dari laporan yang tersimpan dan hasil analisis yang tersedia.
            Lowongan yang masih menunggu atau gagal dianalisis tidak masuk perhitungan persentase.
          </p>
        </section>

        <section aria-label="Metrik utama" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {metrics.map((metric) => (
            <div key={metric.label} className="rounded-2xl border border-slate-200 bg-white p-5">
              <p className="text-sm text-slate-500">{metric.label}</p>
              <p className="mt-2 text-3xl font-semibold tracking-tight">{metric.value}</p>
            </div>
          ))}
        </section>

        <section className="mt-4 rounded-2xl bg-[#123d33] p-6 text-white sm:flex sm:items-center sm:justify-between sm:p-8">
          <div>
            <p className="text-sm text-emerald-100/80">Persentase indikasi age-bias</p>
            <p className="mt-2 text-4xl font-semibold tracking-tight">
              {formatRate(overview.age_bias_rate_pct)}
            </p>
          </div>
          <p className="mt-4 max-w-md text-sm leading-6 text-emerald-50/90 sm:mt-0">
            Proporsi lowongan yang terindikasi membatasi usia dibanding seluruh lowongan yang sudah
            dianalisis.
          </p>
        </section>

        <section className="mt-8">
          <h2 className="mb-4 text-lg font-semibold">Klasifikasi hasil analisis</h2>
          <div className="grid gap-3 sm:grid-cols-3">
            {overview.restriction_breakdown.map((item) => (
              <div
                key={item.restriction_type}
                className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-5 py-4"
              >
                <span className="text-sm font-medium">
                  {restrictionLabels[item.restriction_type]}
                </span>
                <span className="text-lg font-semibold">{formatNumber(item.analyzed_jobs)}</span>
              </div>
            ))}
          </div>
        </section>

        <div className="mt-8 grid gap-5 lg:grid-cols-2">
          <BreakdownTable title="Berdasarkan industri" rows={overview.industry_breakdown} />
          <BreakdownTable title="Berdasarkan level jabatan" rows={overview.job_level_breakdown} />
        </div>

        <p className="mt-8 text-xs leading-5 text-slate-500">
          Data bersifat deskriptif berdasarkan teks lowongan yang dilaporkan, bukan penilaian hukum
          atau kesimpulan tentang seluruh praktik suatu industri maupun perusahaan.
        </p>
      </main>
    </div>
  );
}
