import { NextResponse } from "next/server";

export async function GET(request: Request) {
  const baseUrl = (
    process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1"
  ).replace(/\/+$/, "");
  const incoming = new URL(request.url);
  const query = new URLSearchParams({ lat: incoming.searchParams.get("lat") ?? "", lon: incoming.searchParams.get("lon") ?? "" });
  try {
    const response = await fetch(`${baseUrl}/location/reverse?${query}`, { cache: "no-store" });
    return NextResponse.json(await response.json(), { status: response.status });
  } catch {
    return NextResponse.json({ detail: "Layanan lokasi tidak dapat dihubungi." }, { status: 502 });
  }
}
