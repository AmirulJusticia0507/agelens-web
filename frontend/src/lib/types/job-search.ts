import type { CvJobAiAssessment } from "@/lib/api";

export type JobSearchFilters = {
  cv_file: File;
  location?: string;
  job_type?: string;
  experience_level?: string;
  salary_min?: number;
  salary_max?: number;
  keywords?: string;
};

export type JobSearchResult = {
  job_title: string;
  company_name: string;
  source_platform: string;
  source_url: string | null;
  keyword_match_percentage: number;
  matched_skills: string[];
  ai_assessment: CvJobAiAssessment | null;
  analysis_status: string;
  warnings: string[];
};

export type JobSearchResponse = {
  cv_skills: string[];
  results: JobSearchResult[];
  search_duration_ms: number;
};
