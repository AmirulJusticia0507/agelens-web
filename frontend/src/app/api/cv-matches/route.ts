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
