import Link from "next/link";

import CvMatchForm from "./cv-match-form";

export default function MatchCvPage() {
  return (
    <div className="min-h-screen bg-[#f5f7f5] text-slate-900">
      <header className="border-b border-slate-200/80 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-4 sm:px-8">
          <Link href="/" className="font-semibold tracking-tight">
            ← Agelens
          </Link>
          <Link href="/analytics" className="text-sm text-slate-600 hover:text-emerald-800">
            Analitik
          </Link>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-5 pb-16 sm:px-8">
        <section className="py-10 sm:py-14">
          <p className="text-sm font-medium text-emerald-800">Pencocokan keterampilan</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">
            Bandingkan dua CV dengan lowongan tersimpan
          </h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">
            Unggah dua PDF untuk melihat keterampilan yang terbaca dan perusahaan dengan lowongan
            paling cocok. Pencocokan dilakukan di AgeLens; isi CV tidak disimpan ke database atau
            dikirim ke layanan AI eksternal.
          </p>
        </section>
        <CvMatchForm />
      </main>
    </div>
  );
}
