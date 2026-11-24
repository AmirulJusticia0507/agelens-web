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
  let payload: { cv_session_id?: unknown; profile?: unknown; job_posting_id?: unknown };
  try {
    payload = await request.json();
  } catch {
    return NextResponse.json({ detail: "Permintaan analisis tidak valid." }, { status: 400 });
  }
  if (
    typeof payload.cv_session_id !== "string" ||
    typeof payload.profile !== "string" ||
    typeof payload.job_posting_id !== "string"
  ) {
    return NextResponse.json({ detail: "Data CV atau lowongan tidak valid." }, { status: 422 });
  }

  const baseUrl = (
    process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1"
  ).replace(/\/+$/, "");
  try {
    const response = await fetch(`${baseUrl}/cv-matches/assess-job`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
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
