import Link from "next/link";

export const instant = false;

type Company = {
  id: string;
  display_name: string;
  industry: string | null;
  city: string | null;
  total_jobs_analyzed: number;
  age_restricted_jobs_count: number;
  age_bias_score: number;
};

type CompanyPage = {
  items: Company[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
};

type SearchParams = Record<string, string | string[] | undefined>;

function firstValue(value: string | string[] | undefined): string {
  return Array.isArray(value) ? (value[0] ?? "") : (value ?? "");
}

function pageHref(params: SearchParams, page: number): string {
  const query = new URLSearchParams();
  for (const key of ["q", "industry", "city"]) {
    const value = firstValue(params[key]).trim();
    if (value) query.set(key, value);
  }
  query.set("page", String(page));
  return `/?${query.toString()}`;
}

async function loadCompanies(
  params: URLSearchParams,
): Promise<{ data?: CompanyPage; error?: string }> {
  const baseUrl = (
    process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1"
  ).replace(/\/+$/, "");

  let response: Response;
  try {
    response = await fetch(`${baseUrl}/companies?${params.toString()}`, {
      cache: "no-store",
    });
  } catch {
    return {
      error: "Tidak dapat menghubungi API. Pastikan backend berjalan, lalu muat ulang halaman.",
    };
  }
  if (!response.ok) {
    return { error: `API mengembalikan status ${response.status}. Coba lagi nanti.` };
  }
  try {
    return { data: (await response.json()) as CompanyPage };
  } catch {
    return { error: "Respons dari API tidak dapat dibaca. Coba muat ulang halaman." };
  }
}

function formatScore(score: number): string {
  return new Intl.NumberFormat("id-ID", {
    maximumFractionDigits: 1,
    minimumFractionDigits: 1,
  }).format(score);
}

export default async function Home({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const filters = await searchParams;
  const query = new URLSearchParams();
  for (const key of ["q", "industry", "city"]) {
    const value = firstValue(filters[key]).trim();
    if (value) query.set(key, value);
  }

  const parsedPage = Number.parseInt(firstValue(filters.page), 10);
  const currentPage = Number.isSafeInteger(parsedPage) && parsedPage > 0 ? parsedPage : 1;
  query.set("page", String(currentPage));
  query.set("page_size", "20");

  const result = await loadCompanies(query);
  const data = result.data;
  const numberFormat = new Intl.NumberFormat("id-ID");

  return (
    <div className="min-h-screen bg-[#f5f7f5] text-slate-900">
      <header className="border-b border-slate-200/80 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-4 sm:px-8">
          <Link href="/" className="flex items-center gap-2.5" aria-label="AgeLens beranda">
            <span className="flex size-9 items-center justify-center rounded-xl bg-emerald-700 text-sm font-bold text-white">
              A
            </span>
            <span className="text-lg font-semibold tracking-tight">agelens</span>
          </Link>
          <nav aria-label="Navigasi utama" className="flex items-center gap-6 text-sm">
            <a className="font-medium text-slate-900" href="#hasil">
              Perusahaan
            </a>
            <a className="text-slate-600 transition hover:text-emerald-800" href="#metodologi">
              Tentang skor
            </a>
          </nav>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl px-5 pb-16 sm:px-8">
        <section className="grid gap-10 py-12 md:grid-cols-[1.05fr_0.95fr] md:items-end md:py-16">
          <div>
            <p className="mb-4 inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.12em] text-emerald-800">
              Transparansi dunia kerja
            </p>
            <h1 className="max-w-2xl text-4xl font-semibold leading-tight tracking-tight sm:text-5xl">
              Temukan cerita di balik <span className="text-emerald-800">lowongan kerja.</span>
            </h1>
            <p className="mt-5 max-w-xl text-base leading-7 text-slate-600">
              Telusuri informasi pembatasan usia berdasarkan lowongan yang dianalisis dan bukti
              sumbernya.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-2xl border border-slate-200 bg-white p-5">
              <p className="text-sm text-slate-500">Perusahaan ditemukan</p>
              <p className="mt-2 text-3xl font-semibold tracking-tight">
                {data ? numberFormat.format(data.total) : "—"}
              </p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white p-5">
              <p className="text-sm text-slate-500">Halaman saat ini</p>
              <p className="mt-2 text-3xl font-semibold tracking-tight">
                {data && data.pages > 0 ? `${data.page} / ${data.pages}` : "—"}
              </p>
            </div>
          </div>
        </section>

        <section
          aria-labelledby="search-title"
          className="rounded-3xl bg-[#123d33] p-5 text-white shadow-sm sm:p-7"
        >
          <div className="mb-5">
            <h2 id="search-title" className="text-xl font-semibold">
              Cari perusahaan
            </h2>
            <p className="mt-1 text-sm text-emerald-100/80">
              Gunakan nama, industri, atau kota untuk mempersempit hasil.
            </p>
          </div>
          <form action="/" method="get" className="grid gap-3 md:grid-cols-[1.5fr_1fr_1fr_auto]">
            <label className="sr-only" htmlFor="q">
              Nama perusahaan
            </label>
            <input
              id="q"
              name="q"
              defaultValue={firstValue(filters.q)}
              placeholder="Contoh: Sinar Terang"
              className="h-12 min-w-0 rounded-xl border border-white/15 bg-white px-4 text-sm text-slate-900 outline-none placeholder:text-slate-400 focus:ring-2 focus:ring-emerald-300"
            />
            <label className="sr-only" htmlFor="industry">
              Industri
            </label>
            <input
              id="industry"
              name="industry"
              defaultValue={firstValue(filters.industry)}
              placeholder="Industri"
              className="h-12 min-w-0 rounded-xl border border-white/15 bg-white px-4 text-sm text-slate-900 outline-none placeholder:text-slate-400 focus:ring-2 focus:ring-emerald-300"
            />
            <label className="sr-only" htmlFor="city">
              Kota
            </label>
            <input
              id="city"
              name="city"
              defaultValue={firstValue(filters.city)}
              placeholder="Kota"
              className="h-12 min-w-0 rounded-xl border border-white/15 bg-white px-4 text-sm text-slate-900 outline-none placeholder:text-slate-400 focus:ring-2 focus:ring-emerald-300"
            />
            <button
              type="submit"
              className="h-12 rounded-xl bg-[#c4f06b] px-6 text-sm font-semibold text-slate-900 transition hover:bg-[#d3fa87] focus:outline-none focus:ring-2 focus:ring-white"
            >
              Cari
            </button>
          </form>
        </section>

        <section id="hasil" aria-labelledby="results-title" className="mt-10">
          <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-emerald-800">Direktori</p>
              <h2 id="results-title" className="mt-1 text-2xl font-semibold tracking-tight">
                Perusahaan
              </h2>
            </div>
            {data && (
              <p className="text-sm text-slate-500">
                {numberFormat.format(data.total)} hasil ditemukan
              </p>
            )}
          </div>

          {result.error ? (
            <div
              role="alert"
              className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-sm text-rose-900"
            >
              <p className="font-semibold">Data belum dapat dimuat</p>
              <p className="mt-1">{result.error}</p>
            </div>
          ) : data && data.items.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-300 bg-white px-6 py-14 text-center">
              <p className="text-lg font-semibold">Belum ada perusahaan yang cocok</p>
              <p className="mt-2 text-sm text-slate-500">
                Coba kata kunci lain atau hapus sebagian filter.
              </p>
              <Link
                href="/"
                className="mt-5 inline-flex rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium transition hover:bg-slate-50"
              >
                Hapus filter
              </Link>
            </div>
          ) : (
            <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
              <ul className="divide-y divide-slate-100">
                {data?.items.map((company) => (
                  <li key={company.id}>
                    <Link
                      href={`/companies/${company.id}`}
                      className="group flex flex-col gap-5 p-5 transition hover:bg-emerald-50/50 sm:flex-row sm:items-center sm:justify-between sm:px-6"
                    >
                      <div className="flex min-w-0 items-center gap-4">
                        <span className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-emerald-50 text-lg font-semibold text-emerald-800">
                          {company.display_name.charAt(0).toUpperCase()}
                        </span>
                        <div className="min-w-0">
                          <h3 className="truncate font-semibold group-hover:text-emerald-800">
                            {company.display_name}
                          </h3>
                          <p className="mt-1 truncate text-sm text-slate-500">
                            {[company.industry, company.city].filter(Boolean).join(" · ") ||
                              "Industri dan lokasi belum tersedia"}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center justify-between gap-8 sm:justify-end">
                        <div className="text-sm">
                          <p className="font-semibold text-slate-900">
                            {company.total_jobs_analyzed > 0
                              ? `${formatScore(company.age_bias_score)}%`
                              : "—"}
                          </p>
                          <p className="mt-1 text-xs text-slate-500">
                            {company.total_jobs_analyzed > 0
                              ? "indikasi age-bias"
                              : "belum dianalisis"}
                          </p>
                        </div>
                        <div className="text-right text-sm">
                          <p className="font-medium text-slate-700">
                            {numberFormat.format(company.age_restricted_jobs_count)} /{" "}
                            {numberFormat.format(company.total_jobs_analyzed)}
                          </p>
                          <p className="mt-1 text-xs text-slate-500">dibatasi / dianalisis</p>
                        </div>
                        <span
                          aria-hidden="true"
                          className="hidden text-xl text-slate-400 transition group-hover:translate-x-1 group-hover:text-emerald-800 sm:block"
                        >
                          →
                        </span>
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {data && data.pages > 1 && (
            <nav aria-label="Navigasi halaman hasil" className="mt-6 flex justify-center gap-3">
              {data.page > 1 ? (
                <Link
                  href={pageHref(filters, data.page - 1)}
                  className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium transition hover:bg-slate-50"
                >
                  Sebelumnya
                </Link>
              ) : (
                <span className="rounded-lg border border-slate-200 px-4 py-2 text-sm text-slate-400">
                  Sebelumnya
                </span>
              )}
              <span className="px-2 py-2 text-sm text-slate-600">
                Halaman {data.page} dari {data.pages}
              </span>
              {data.page < data.pages ? (
                <Link
                  href={pageHref(filters, data.page + 1)}
                  className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium transition hover:bg-slate-50"
                >
                  Berikutnya
                </Link>
              ) : (
                <span className="rounded-lg border border-slate-200 px-4 py-2 text-sm text-slate-400">
                  Berikutnya
                </span>
              )}
            </nav>
          )}
        </section>

        <section
          id="metodologi"
          className="mt-10 rounded-2xl border border-slate-200 bg-white p-6 sm:p-8"
        >
          <p className="text-sm font-semibold text-emerald-800">Cara membaca data</p>
          <h2 className="mt-2 text-xl font-semibold tracking-tight">
            Bukti lebih penting dari sekadar angka.
          </h2>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">
            Skor menunjukkan persentase lowongan yang sudah dianalisis dan memiliki indikasi
            pembatasan usia. Hasil merupakan ringkasan berbasis teks lowongan yang tersedia, bukan
            penilaian hukum atau kesimpulan tentang seluruh praktik perusahaan.
          </p>
        </section>
      </main>
    </div>
  );
}
