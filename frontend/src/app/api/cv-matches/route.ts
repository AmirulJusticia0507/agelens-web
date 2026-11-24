import { NextResponse } from "next/server";

export async function POST(request: Request) {
  let formData: FormData;
  try {
    formData = await request.formData();
  } catch {
    return NextResponse.json(
      { detail: "Form unggahan tidak dapat dibaca. Pilih ulang kedua file CV." },
      { status: 400 },
    );
  }

  const baseUrl = (
    process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1"
  ).replace(/\/+$/, "");

  try {
    const response = await fetch(`${baseUrl}/cv-matches/analyze`, {
      method: "POST",
      body: formData,
      cache: "no-store",
    });
    const body: unknown = await response.json();
    return NextResponse.json(body, { status: response.status });
  } catch {
    return NextResponse.json(
      { detail: "Tidak dapat menghubungi API AgeLens. Pastikan backend berjalan." },
      { status: 502 },
    );
  }
}

export async function PUT(request: Request) {
  let formData: FormData;
  try {
    formData = await request.formData();
  } catch {
    return NextResponse.json({ detail: "Form analisis tidak valid." }, { status: 400 });
  }
  const cvFile = formData.get("cv_file");
  const jobPostingId = formData.get("job_posting_id");
  if (!(cvFile instanceof File) || typeof jobPostingId !== "string" || !jobPostingId) {
    return NextResponse.json(
      { detail: "File CV atau lowongan tidak ditemukan. Unggah CV kembali sebelum analisis AI." },
      { status: 422 },
    );
  }

  const baseUrl = (
    process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1"
  ).replace(/\/+$/, "");
  try {
    const response = await fetch(`${baseUrl}/cv-matches/assess-job`, {
      method: "POST",
      body: formData,
      cache: "no-store",
    });
    return NextResponse.json(await response.json(), { status: response.status });
  } catch {
    return NextResponse.json(
      { detail: "Tidak dapat menghubungi layanan analisis AI. Coba lagi." },
      { status: 502 },
    );
  }
}
