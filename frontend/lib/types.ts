export type Id = string;

// Where a line came from: the onboarding check against the user's own documents.
export interface Provenance {
  ok: boolean; reason: string | null; doc?: string | null; snippet?: string | null; coverage?: number;
  trimmed?: string[]; restored_by_user?: boolean; edited_by_user?: boolean;
}

// `confirmed` means usable: backed by the user's documents, or written or restored by them.
export interface Bullet {
  id: Id; item_id: Id; text: string; confirmed: boolean; has_metric: boolean; sort: number; provenance?: Provenance | null;
}
export interface Item {
  id: Id; key: string; kind: "project" | "experience"; name: string; tagline: string | null;
  period: string | null; stack: string | null; stack_label: string; links: { text: string; url: string }[];
  confirmed: boolean; sort: number; bullets: Bullet[]; provenance?: Provenance | null;
}
export interface Entry {
  id: Id; lead: string | null; text: string; tracks: string[] | null; confirmed: boolean; provenance?: Provenance | null;
}
export interface Section { id: Id; key: "awards" | "roles"; heading: string; entries: Entry[] }
export interface Education {
  id: Id; institution: string; degree: string | null; meta: string | null; result: string | null;
  lines: string[]; confirmed: boolean; provenance?: Provenance | null;
}
export interface Fact {
  id: Id; kind: string; text: string; source: string; confirmed_at: string | null; evidence_items: string[];
  provenance?: Provenance | null;
}
export interface FactBank { items: Item[]; sections: Section[]; education: Education[]; facts: Fact[] }

export interface Preferences {
  role_types: string[]; open_to: string[]; locations: string[]; remote_ok: boolean; onsite_ok: boolean;
  hybrid_ok: boolean; stipend_floor: number | null; currency: string; unpaid_remote_policy: string;
  unpaid_onsite_policy: string; excluded_company_types: string[]; excluded_companies: string[];
  freshness_ceiling_hours: number; duration_flex: string; start_date: string; signature_html: string | null;
  desired_roles: string[]; target_roles: string[]; target_families: string[];
  salary_floor: number | null; notice_period: string | null;
}
export interface Profile {
  name: string | null; headline: string | null; location: string | null; phone: string | null;
  email: string | null; links: { text: string; url: string }[]; grad_date: string | null;
  batch_year: number | null; cgpa: number | null; onboarding_step: string; consent_version: string | null;
  github_url: string | null; about: string | null;
  career_stage: Stage | null; experience_years: number | null; experience_band: string | null;
  portfolio_url: string | null; linkedin_url: string | null; build: Build;
}

export type Stage = "student" | "graduate" | "experienced";
export type Fit = "strong" | "good" | "stretch";

/** The background onboarding build, as profiles.build records it. */
export interface Build {
  status?: "queued" | "running" | "done" | "failed";
  step?: "reading" | "checking" | "writing" | "rendering" | "done";
  error?: string | null; started_at?: string; finished_at?: string;
  kept?: number; left_out?: number;
  suggestions?: { family: string; label: string; why: string }[];
  github?: { username: string; read: boolean }; portfolio?: { url: string; read: boolean };
  failed_tracks?: Record<string, string>;
}

export interface LeftOut {
  kind: "item" | "bullet" | "entry" | "education" | "skill"; id: Id; text: string; context: string | null;
  reason: string | null;
}
export interface Review {
  profile: Pick<Profile, "name" | "career_stage" | "experience_years" | "experience_band" | "build" |
    "onboarding_step" | "grad_date" | "batch_year">;
  preferences: Pick<Preferences, "target_families" | "desired_roles">;
  item_names: Record<string, string>;
  counts: { items: number; bullets: number; skills: number };
  tracks: Track[]; left_out: LeftOut[]; suggestions: NonNullable<Build["suggestions"]>;
}
export interface Me {
  user: { id: Id; email: string | null }; profile: Profile; preferences: Preferences;
  counts: { items: number; bullets: number; tracks: number; applications: number };
  consent_version: string; needs_consent: boolean;
}

export interface Track {
  id: Id; key: string; label: string; title_line: string; summary: string;
  left_sections: { heading: string; item_keys: string[] }[]; skills: { label: string; items: string }[];
  scale: number | null; approved: boolean; role_family: string | null; fit: Fit | null; fit_why: string | null;
  gaps: string[];
  baseline: { id: Id; scale: number; ats_score: number | null; dropped_ids?: string[]; created_at?: string } | null;
}

export interface Lead {
  id: Id; status: "queued" | "processing" | "done" | "failed"; error: string | null; source_ref: string | null;
  first_seen_at: string; posted_age_hours: number | null; title: string | null; company_name: string | null;
  location: string | null; decision: "keep" | "drop" | "flag" | null; reasons: string[] | null;
  flags: string[] | null; overridden: boolean | null; rank: number | null; track_key: string | null;
  verification: string | null; application_id: Id | null; application_status: string | null;
}

export interface Application {
  id: Id; job_id: Id; company_name: string | null; poster_name: string | null; role_title: string | null;
  track_key: string | null; route: "email" | "portal"; apply_to: string | null; status: string;
  age_at_capture_hours: number | null; age_at_draft_hours: number | null; judgment_calls: string[];
  notes: string | null; created_at: string; user_marked_sent_at: string | null; lint_ok: boolean | null;
  domain: string | null; verification: string | null; business_summary: string | null; source_ref: string | null;
  source: string; resume_id: Id | null; resume_filename: string | null;
}
export interface ResumeLink { token: string; url: string; opens: number; last_opened_at: string | null; created_at: string }
export interface LintCheck { check: string; ok: boolean; detail: string }
export interface Draft {
  id: Id; to_addrs: string[]; subject: string; html: string; plain: string; lint: LintCheck[];
  lint_ok: boolean; gmail_url: string | null; version: number;
}
export interface EventRow { id: Id; type: string; occurred_at: string; deadline_at: string | null; summary: string | null }
export interface AppDetail {
  application: Application; draft: Draft | null;
  resume: { id: Id; track_key: string; scale: number; pages_verified: number; renderer: string;
            ats_score: number | null; jd_match: number | null; dropped_ids: string[]; filename: string;
            link: ResumeLink | null } | null;
  events: EventRow[]; job: { raw_text: string; extracted: Record<string, unknown> | null };
}
