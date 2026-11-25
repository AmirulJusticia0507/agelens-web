# Implementation Plan: Job Search Tab for Match-CV Page

## Overview
Add a second tab "Cari dari berbagai sumber" (Search from multiple sources) to the existing `/match-cv` page. The tab enables users to search jobs from multiple sources (Indeed, LinkedIn, remote.io) and analyze CV fit using the backend endpoint `POST /api/v1/cv-matches/search-and-analyze`.

## Key Architecture Decisions

1. **Tab State Management**: Use React hooks (`useState`) within CvMatchForm to track the active tab and search state. The CV file is shared between tabs via state lifting—upload once, reuse for both features.

2. **Component Structure**: 
   - Modify `CvMatchForm` to include a tab switcher
   - Create `JobSearchTab` component for the new feature (search form + results display)
   - Create `JobSearchResults` component to render result cards
   - Keep `CvResults` unchanged for the existing tab

3. **TypeScript Types**: Define types in a new file `src/lib/types/job-search.ts` to match backend schemas (JobSearchFilters, JobSearchResult, JobSearchResponse).

4. **Error Handling**: 
   - 400/422: CV validation or parameter errors → user-friendly message
   - 404: No jobs found → "Tidak ada lowongan ditemukan"
   - 503/502: LLM/service unavailable → "Layanan analisis AI tidak tersedia"
   - Network errors → "Tidak dapat menghubungi layanan"

5. **Loading & Empty States**:
   - Show spinner during search with "Mencari lowongan..." message
   - Display empty state if no jobs match
   - Show partial results if some sources fail (warnings from backend)

6. **Styling**: Match existing emerald-800, sky-50, [#123d33], [#c4f06b] color scheme. Use Tailwind classes consistently with the rest of the app.

7. **Next.js 16 Patterns**: Use Client Component ("use client") with React hooks; no App Router static generation needed for this feature since it's fully dynamic.

---

## Implementation Steps

### Step 1: Create Job Search Type Definitions
**What**: Define TypeScript types for job search filters, results, and responses in a new file. These match the backend schema.

**Files**: 
- `src/lib/types/job-search.ts` (create)

**Verify**: 
```bash
npm run lint
```
Expected: No type errors in the new file.

---

### Step 2: Extend src/lib/api.ts with JobSearch Types
**What**: Add the new types (JobSearchFilters, JobSearchResult, JobSearchResponse) as exports to the existing api.ts file so they can be imported alongside CvJobAiAssessment.

**Files**: 
- `src/lib/api.ts` (modify)

**Verify**: 
```bash
npm run lint
```
Expected: No type errors; types are properly exported and can be imported.

---

### Step 3: Create JobSearchResults Component
**What**: Build a component to display search results. Each result card shows:
- Job title, company name, source platform
- Keyword match percentage badge (emerald background)
- Matched skills list
- AI assessment (if available, in sky-50 box) or loading/error state
- Link to source URL (if safe)

Place inline error handling for missing assessments and display warnings from backend.

**Files**: 
- `src/app/match-cv/job-search-results.tsx` (create)

**Verify**: 
```bash
npm run build
```
Expected: No type errors, component compiles without warnings.

---

### Step 4: Create JobSearchTab Component
**What**: Build the search form and integration component:
- Form fields: location, job_type, experience_level, salary_min/max, keywords (all optional)
- CV file upload is handled by parent; this component just displays upload status
- Submit button that calls POST /api/v1/cv-matches/search-and-analyze with FormData
- Error display (validation, network, HTTP errors)
- Loading state with spinner
- Render JobSearchResults when results available
- Display warnings from backend (e.g., "Failed to fetch from LinkedIn")
- Show total search duration and results count

**Files**: 
- `src/app/match-cv/job-search-tab.tsx` (create)

**Verify**: 
```bash
npm run build
```
Expected: No type errors, compiles without warnings.

---

### Step 5: Refactor CvMatchForm to Add Tabs
**What**: 
- Add tab state (`"stored_jobs" | "search_jobs"`) to CvMatchForm
- Add tab switcher UI at the top of the form (two buttons: "Cocokkan dengan lowongan tersimpan" and "Cari dari berbagai sumber")
- Conditionally render CvResults (existing) or JobSearchTab (new) based on active tab
- Keep CV upload form visible always (above tabs) so it's shared between tabs
- Share `cvFiles` state with JobSearchTab via props
- Ensure active tab styling uses emerald-800 for text and sky-50 for active tab background

**Files**: 
- `src/app/match-cv/cv-match-form.tsx` (modify)

**Verify**: 
```bash
npm run build
```
Expected: No type errors, component compiles and renders without warnings.

---

### Step 6: Full Build and Browser Testing
**What**: Run the full build and verify no runtime errors; test the UI in a browser:
- Load /match-cv page
- Verify both tabs are visible and can be clicked
- Upload a CV to tab 1; verify results display (or expected error message)
- Switch to tab 2; verify CV upload is retained
- Enter search filters and click "Cari lowongan"
- Verify loading state appears, then results display (or error message)
- Verify error messages are user-friendly (HTTP status handled correctly)
- Verify matched skills display and AI assessments show when available
- Test responsive layout on mobile (tabs should stack/stay accessible)

**Files**: 
- All created/modified files

**Verify**: 
```bash
npm run build
```
Expected: Build succeeds with no errors or warnings.

---

## Files Summary

| Path | Action | Purpose |
|------|--------|---------|
| `src/lib/types/job-search.ts` | Create | TypeScript types for job search (filters, results, response) |
| `src/lib/api.ts` | Modify | Export job search types alongside existing types |
| `src/app/match-cv/job-search-results.tsx` | Create | Component to display search results with result cards |
| `src/app/match-cv/job-search-tab.tsx` | Create | Search form and results integration |
| `src/app/match-cv/cv-match-form.tsx` | Modify | Add tab switcher, integrate JobSearchTab, share CV file state |

---

## Error Handling Details

### HTTP Status Codes
- **400 Bad Request**: Malformed parameters → show form validation errors
- **404 Not Found**: No jobs found from any source → "Tidak ada lowongan ditemukan dari sumber yang tersedia. Coba ubah filter pencarian."
- **422 Unprocessable Entity**: CV text extraction failed or no skills found → show backend error message
- **502 Bad Gateway**: LLM analysis unavailable → "Layanan analisis AI sementara tidak tersedia. Silakan coba lagi dalam beberapa saat."
- **503 Service Unavailable**: Job fetcher timeout/unavailable → "Pencarian lowongan gagal. Silakan coba lagi."
- **500 Internal Server Error**: Backend error → "Terjadi kesalahan pada server. Silakan coba lagi."
- **Network Timeout**: Fetch request timeout → "Tidak dapat menghubungi layanan. Pastikan koneksi internet aktif dan coba lagi."

### Warning Handling
Display warnings from `JobSearchResponse.warnings` (e.g., "Failed to fetch jobs from LinkedIn") in a yellow/amber alert box, but allow results to display if any jobs were found.

---

## Component API Design

### JobSearchTab Props
```typescript
interface JobSearchTabProps {
  cvFile: File | null;
  cvText?: string; // optional; computed from cvFile if not provided
  disabled?: boolean; // true while parent is uploading CV
}
```

### JobSearchResults Props
```typescript
interface JobSearchResultsProps {
  results: JobSearchResult[];
  cvSkills: string[];
  searchDurationMs: number;
  warnings: string[];
  isLoading: boolean; // show spinner while loading AI assessments
}
```

---

## Accessibility & UX Notes

- Use semantic HTML (`<section>`, `<button>`, `<form>`)
- Include `aria-live="polite"` for results that appear after async operations
- Form labels must be associated with inputs via `htmlFor`
- Error messages must have `role="alert"`
- Tab switcher should use keyboard navigation (Tab key to focus, Enter/Space to activate)
- Loading state should show spinner and disable inputs
- Responsive layout: stack tabs on mobile, ensure touch targets ≥44px

---

## Testing Checklist (Manual)

- [x] Build verification passed: npm run build completed successfully
- [x] TypeScript check passed: npx tsc --noEmit completed without errors  
- [x] ESLint check passed: npx eslint completed without errors
- [ ] Upload CV to tab 1; switch to tab 2; CV file is retained
- [ ] Enter search filters (all optional) and click "Cari lowongan"
- [ ] Verify loading state ("Mencari lowongan...") appears
- [ ] After 5+ seconds, results appear with job cards
- [ ] Each result shows job title, company, source, match %, skills, AI assessment
- [ ] Click "Buka sumber lowongan" link; opens in new tab (safe URL)
- [ ] If AI assessment failed, show "timeout" or "error" status gracefully
- [ ] Warnings from backend display in amber alert
- [ ] Empty state: no jobs found shows appropriate message
- [ ] Network error: shows connection error message
- [ ] Tab switcher styling: active tab has emerald text, inactive has gray text
- [ ] Responsive: layout works on mobile (tabs stack, buttons are touchable)
