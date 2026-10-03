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
  source: "paste" | "agent"; found_by: string | null;
  first_seen_at: string; posted_age_hours: number | null; title: string | null; company_name: string | null;
  location: string | null; decision: "keep" | "drop" | "flag" | null; reasons: string[] | null;
  flags: string[] | null; overridden: boolean | null; rank: number | null; track_key: string | null;
  verification: string | null; application_id: Id | null; application_status: string | null;
  match_id: Id | null; score: number | null; bucket: Bucket | null; prepare_status: PrepareStatus | null;
  prepare_error: string | null;
}

/** A personal key the person's own agent uses to send the posts it finds (shown once when made). */
export interface IntakeKey { id: Id; name: string; prefix: string; created_at: string; last_used_at: string | null }

// ------------------------------------------------------------------ opportunities (matches)

export type Bucket = "strong" | "good" | "gaps";
export type PrepareStatus = "queued" | "running" | "done" | "failed";
/** Where an address was published: the post, the company's own site, or its general inbox. */
export type ContactContext = "post_apply" | "careers_page" | "site_generic";

/** One opening as it suits one person: score, reasons and gaps are theirs alone. */
export interface Opportunity {
  id: Id; job_id: Id; score: number | null; bucket: Bucket | null; why: string[]; gaps: string[];
  decision: "keep" | "drop"; reasons: string[]; overridden: boolean; track_key: string | null;
  prepare_status: PrepareStatus | null; prepare_error: string | null; seen_at: string | null;
  dismissed_at: string | null; route: "email" | "portal" | null; apply_to: string | null; flags: string[] | null;
  title: string | null; company_name: string | null; role_family: string | null; employment_type: string | null;
  work_mode: "remote" | "hybrid" | "onsite" | "unknown" | null; city: string | null;
  exp_min: number | null; exp_max: number | null; pay_min: number | null; pay_max: number | null;
  pay_currency: string | null; pay_period: "month" | "year" | "total" | null;
  skills_must: string[]; skills_nice: string[]; source: string; source_ref: string | null;
  visibility: "private" | "public"; first_seen_at: string; age_hours: number | null;
  domain: string | null; verification: string | null;
  contact_email: string | null; contact_name: string | null; contact_role: string | null;
  contact_context: ContactContext | null; application_id: Id | null; application_status: string | null;
}
export interface ContactCandidate {
  id: Id; email: string; person_name: string | null; person_role: string | null; context: ContactContext;
  source_url: string | null; evidence: string | null; is_generic: boolean; domain_matches: boolean | null;
  confidence: number; chosen: boolean; where: string;
}
export interface OpportunityDetail extends Opportunity {
  job: { raw_text: string; extracted: Record<string, unknown> | null };
  company: { name: string; domain: string | null; verification: string | null; business_summary: string | null;
             flags: string[] } | null;
  contacts: ContactCandidate[];
}
export interface Today {
  deadlines: { id: Id; type: string; deadline_at: string | null; summary: string | null; application_id: Id;
               company_name: string | null; role_title: string | null }[];
  ready: Application[];
  groups: Record<Bucket, Opportunity[]>;
  decisions: Lead[];
  number_gaps: { id: Id; text: string; item_name: string }[];
  processing: number;
  me: { name: string | null; career_stage: Stage | null; experience_years: number | null;
        experience_band: string | null; target_families: string[] | null } | null;
}

export interface Application {
  id: Id; job_id: Id; company_name: string | null; poster_name: string | null; role_title: string | null;
  track_key: string | null; route: "email" | "portal"; apply_to: string | null; status: string;
  age_at_capture_hours: number | null; age_at_draft_hours: number | null; judgment_calls: string[];
  notes: string | null; created_at: string; user_marked_sent_at: string | null; lint_ok: boolean | null;
  domain: string | null; verification: string | null; business_summary: string | null; source_ref: string | null;
  source: string; resume_id: Id | null; resume_filename: string | null; in_gmail: boolean | null;
}
export interface ResumeLink { token: string; url: string; opens: number; last_opened_at: string | null; created_at: string }
export interface LintCheck { check: string; ok: boolean; detail: string }
export interface Draft {
  id: Id; to_addrs: string[]; subject: string; html: string; plain: string; lint: LintCheck[];
  lint_ok: boolean; gmail_url: string | null; version: number;
  /** Set once the letter is a draft in the person's own Gmail. */
  gmail_draft_id: string | null; gmail_message_id: string | null; gmail_drafted_at: string | null;
  gmail_error: string | null; gmail_link: string | null;
}

/** The person's Gmail connection: letters are created as drafts there. */
export interface GmailStatus {
  available: boolean; connected: boolean; expired: boolean; email: string | null; connected_at: string | null;
}
export interface EventRow { id: Id; type: string; occurred_at: string; deadline_at: string | null; summary: string | null }
export interface AppDetail {
  application: Application; draft: Draft | null;
  resume: { id: Id; track_key: string; scale: number; pages_verified: number; renderer: string;
            ats_score: number | null; jd_match: number | null; dropped_ids: string[]; filename: string;
            link: ResumeLink | null } | null;
  events: EventRow[]; job: { raw_text: string; extracted: Record<string, unknown> | null };
  match: { id: Id; score: number | null; bucket: Bucket | null; why: string[]; gaps: string[] } | null;
  contact: { email: string; person_name: string | null; person_role: string | null; context: ContactContext;
             source_url: string | null; evidence: string | null; where: string } | null;
}
