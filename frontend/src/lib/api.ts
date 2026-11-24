export type CompanySummary = {
  id: string;
  normalized_name: string;
  display_name: string;
  industry: string | null;
  city: string | null;
  total_jobs_analyzed: number;
  age_restricted_jobs_count: number;
  age_bias_score: number;
  created_at: string;
  updated_at: string;
};

export type CompanyPage = {
  items: CompanySummary[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
};

export type AgeAnalysis = {
  has_age_restriction: boolean;
  restriction_type: "EXPLICIT" | "IMPLICIT" | "NONE";
  min_age: number | null;
  max_age: number | null;
  extracted_evidence: string | null;
  ai_reasoning: string | null;
  confidence_score: number | null;
  model_used: string | null;
  analyzed_at: string;
};

export type JobPosting = {
  id: string;
  job_title: string;
  job_level: string | null;
  source_platform: string;
  source_url: string | null;
  raw_description: string;
  posted_date: string | null;
  scraped_at: string;
  analysis_status: "pending" | "processing" | "completed" | "failed";
  analysis: AgeAnalysis | null;
};

export type CompanyDetail = CompanySummary & {
  job_postings: JobPosting[];
};

export type CvJobMatch = {
  job_posting_id: string;
  job_title: string;
  source_platform: string;
  source_url: string | null;
  match_percentage: number;
  matched_skills: string[];
  summary_only: boolean;
};

export type CvJobAiAssessment = {
  summary: string;
  strengths: string[];
  gaps: string[];
  fit_level: "strong" | "moderate" | "low";
  caveat: string;
};

export type CvCompanyMatch = {
  company_id: string;
  display_name: string;
  match_percentage: number;
  matched_skills: string[];
  jobs: CvJobMatch[];
};

export type CvProfileMatch = {
  label: "CV 1" | "CV 2";
  skills: string[];
  jobs_considered: number;
  companies: CvCompanyMatch[];
};

export type CvMatchResponse = {
  profiles: CvProfileMatch[];
};

export type CategoryAnalytics = {
  category: string | null;
  analyzed_jobs: number;
  restricted_jobs: number;
  age_bias_rate_pct: number;
};

export type AnalyticsOverview = {
  total_companies: number;
  total_submissions: number;
  analyzed_jobs: number;
  restricted_jobs: number;
  age_bias_rate_pct: number;
  restriction_breakdown: {
    restriction_type: "EXPLICIT" | "IMPLICIT" | "NONE";
    analyzed_jobs: number;
  }[];
  industry_breakdown: CategoryAnalytics[];
  job_level_breakdown: CategoryAnalytics[];
};

export type ApiResult<T> =
  | { data: T; status: number }
  | { error: string; status: number | null };

export async function fetchApi<T>(path: string): Promise<ApiResult<T>> {
  const baseUrl = (
    process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1"
  ).replace(/\/+$/, "");

  let response: Response;
  try {
    response = await fetch(`${baseUrl}/${path.replace(/^\/+/, "")}`, {
      cache: "no-store",
    });
  } catch {
    return {
      error: "Tidak dapat menghubungi API. Pastikan backend berjalan, lalu muat ulang halaman.",
      status: null,
    };
  }
  if (!response.ok) {
    return {
      error: `API mengembalikan status ${response.status}. Coba lagi nanti.`,
      status: response.status,
    };
  }

  try {
    return { data: (await response.json()) as T, status: response.status };
  } catch {
    return {
      error: "Respons dari API tidak dapat dibaca. Coba muat ulang halaman.",
      status: response.status,
    };
  }
}
