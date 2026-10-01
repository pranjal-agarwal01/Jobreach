// Demo mode: every screen filled with a made-up student (the synthetic "Aarav Mehta" test
// profile) and fictional companies on .example domains, so the signed-in UI can be reviewed
// without an account. Development builds only; turned on at /demo and off from the banner.
import type {
  AppDetail, Application, FactBank, Lead, Me, ResumeLink, RoleOption, Track,
} from "./types";

const KEY = "jobreach-demo";

export function isDemo(): boolean {
  if (process.env.NODE_ENV === "production" || typeof window === "undefined") return false;
  try { return window.localStorage.getItem(KEY) === "1"; } catch { return false; }
}
export function setDemo(on: boolean) {
  try {
    if (on) window.localStorage.setItem(KEY, "1");
    else window.localStorage.removeItem(KEY);
  } catch { /* storage blocked: demo stays off */ }
}

const ago = (h: number) => new Date(Date.now() - h * 3600_000).toISOString();
const ahead = (h: number) => new Date(Date.now() + h * 3600_000).toISOString();

const SIGNATURE = `<p>Best regards,<br>Aarav Mehta<br>+91 90000 00001 | aarav.mehta@example.com</p>`;

const me: Me = {
  user: { id: "demo-user", email: "aarav.mehta@example.com" },
  profile: {
    name: "Aarav Mehta", headline: "Backend Developer", location: "Pune, Maharashtra, India",
    phone: "+91 90000 00001", email: "aarav.mehta@example.com",
    links: [{ text: "github.com/aarav-mehta-example", url: "https://github.com/aarav-mehta-example" }],
    grad_date: "May 2027", batch_year: 2027, cgpa: 8.1, onboarding_step: "done", consent_version: "2026-10-01",
    github_url: "https://github.com/aarav-mehta-example", about: "Final-year IT student who likes backend work.",
  },
  preferences: {
    role_types: ["backend", "sde", "fullstack"], open_to: ["internship"], locations: ["Pune", "Bengaluru", "Remote"],
    remote_ok: true, onsite_ok: true, hybrid_ok: true, stipend_floor: 10000, currency: "INR",
    unpaid_remote_policy: "draft_with_floor", unpaid_onsite_policy: "drop", excluded_company_types: ["big_tech"],
    excluded_companies: [], freshness_ceiling_hours: 72, duration_flex: "Flexible on duration",
    start_date: "Immediately", signature_html: null, desired_roles: ["Backend Developer Intern"],
    target_roles: ["Backend Developer Intern", "Full-stack Developer Intern"], pool_mode: "mix",
  },
  counts: { items: 2, bullets: 6, tracks: 1, applications: 6 },
  consent_version: "2026-10-01", needs_consent: false,
};

interface Co { id: string; company: string; domain: string; role: string; status: string; route: "email" | "portal";
  draftAge: number; created: number; summary: string; poster: string | null; calls: string[]; sentAt?: number }

const COS: Co[] = [
  { id: "a1", company: "Kitebox Labs", domain: "kitebox.example", role: "Backend Developer Intern", status: "drafted",
    route: "email", draftAge: 1.6, created: 0.5, poster: "Riya Sharma",
    summary: "Builds route-planning software for small courier companies in tier-2 cities.", calls: [] },
  { id: "a2", company: "Ledgerleaf", domain: "ledgerleaf.example", role: "Full-stack Developer Intern", status: "drafted",
    route: "email", draftAge: 7.5, created: 3, poster: "Kabir Anand",
    summary: "Bookkeeping app for kirana stores that reads printed bills from photos.", calls: [] },
  { id: "a3", company: "Monsoon Robotics", domain: "monsoonrobotics.example", role: "Software Engineer Intern", status: "needs_review",
    route: "email", draftAge: 26, created: 20, poster: "Neha Iyer",
    summary: "Makes warehouse picking robots for mid-sized distributors.",
    calls: ["Contact domain (gmail.com) differs from the website domain (monsoonrobotics.example)"] },
  { id: "a4", company: "Tessera Analytics", domain: "tessera.example", role: "Backend Engineer Intern", status: "interview",
    route: "email", draftAge: 3, created: 120, poster: "Arjun Mehra", sentAt: 118,
    summary: "Dashboards for clinics that track patient wait times.", calls: [] },
  { id: "a5", company: "Quillstack", domain: "quillstack.example", role: "SDE Intern", status: "sent",
    route: "email", draftAge: 5, created: 52, poster: "Sana Qureshi", sentAt: 50,
    summary: "Writing tools for vernacular news desks.", calls: [] },
  { id: "a6", company: "Pinewheel Health", domain: "pinewheel.example", role: "Backend Intern", status: "drafted",
    route: "portal", draftAge: 30, created: 28, poster: null,
    summary: "Appointment booking for physiotherapy clinics.", calls: [] },
];

function application(c: Co): Application {
  return {
    id: c.id, job_id: "j" + c.id, company_name: c.company, poster_name: c.poster, role_title: c.role, track_key: "sde",
    route: c.route, apply_to: c.route === "email" ? `careers@${c.domain}` : `https://jobs.${c.domain}/apply/backend-intern`,
    status: c.status, age_at_capture_hours: Math.max(0.2, c.draftAge - 0.3), age_at_draft_hours: c.draftAge,
    judgment_calls: c.calls, notes: null, created_at: ago(c.created),
    user_marked_sent_at: c.sentAt !== undefined ? ago(c.sentAt) : null, lint_ok: c.status !== "needs_review",
    domain: c.domain, verification: c.calls.length ? "flag" : "pass", business_summary: c.summary,
    source_ref: null, source: "paste", resume_id: "r" + c.id, resume_filename: "resume_Aarav_Mehta.pdf",
  };
}

function draftFor(c: Co) {
  const first = c.poster?.split(" ")[0] ?? "there";
  const paras = [
    `Hi ${first},`,
    `I saw your post about the ${c.role} role at ${c.company}. I'm a final-year B.Tech IT student at Deccan Institute of Technology, and backend work that has to keep running under load is what I enjoy most.`,
    `At my college fest I built QueueKit, a Postgres-backed job queue that took lost registration emails from about 40 to zero in fest week. I also built CampusBites, a canteen pre-order API that served 1,200 orders in its first month with p95 response times under 120 ms.`,
    `I can start immediately and I'm flexible on duration. My resume is attached. Would you be open to a short call this week?`,
  ];
  const html = paras.map((p) => `<p>${p}</p>`).join("") + SIGNATURE;
  const plain = paras.join("\n\n") + "\n\nBest regards,\nAarav Mehta\n+91 90000 00001 | aarav.mehta@example.com";
  const checks = ["no_em_dash", "no_bare_urls", "html_well_formed", "no_placeholders", "recipient_published", "numbers_backed",
    "length", "resume_attached", "one_role", "availability_not_narrowed", "stipend_rule", "signature_verbatim"];
  const lint = checks.map((check) => ({
    check, ok: !(c.status === "needs_review" && check === "recipient_published"),
    detail: c.status === "needs_review" && check === "recipient_published" ? "neha.iyer@gmail.com is not on the company's website" : "",
  }));
  return {
    id: "d" + c.id, to_addrs: [c.status === "needs_review" ? "neha.iyer@gmail.com" : `careers@${c.domain}`],
    subject: `${c.role} application: Aarav Mehta (B.Tech IT, 2027)`, html, plain, lint, lint_ok: c.status !== "needs_review",
    gmail_url: null, version: 1,
  };
}

let links: Record<string, ResumeLink> = {
  ra5: { token: "demoQuill12", url: "http://localhost:8000/r/demoQuill12", opens: 3, last_opened_at: ago(30), created_at: ago(50) },
};

function detail(id: string): AppDetail {
  const c = COS.find((x) => x.id === id) ?? COS[0];
  const app = application(c);
  return {
    application: app,
    draft: c.route === "email" ? draftFor(c) : null,
    resume: {
      id: "r" + c.id, track_key: "sde", scale: 1.04, pages_verified: 1, renderer: "LibreOffice 26.8",
      ats_score: 82.5, jd_match: 64, dropped_ids: [], filename: "resume_Aarav_Mehta.pdf", link: links["r" + c.id] ?? null,
    },
    events: c.status === "interview"
      ? [{ id: "e2", type: "interview", occurred_at: ago(20), deadline_at: ahead(26), summary: "30-minute call with the CTO" },
         { id: "e1", type: "sent", occurred_at: ago(118), deadline_at: null, summary: "Marked sent" }]
      : c.sentAt !== undefined ? [{ id: "e1", type: "sent", occurred_at: ago(c.sentAt), deadline_at: null, summary: "Marked sent" }] : [],
    job: {
      raw_text: `${c.poster ?? c.company}\n${c.poster ? "Founder at " + c.company + "\n" : ""}${Math.round(c.draftAge)}h\n\nWe're hiring a ${c.role} (6 months, Rs 15,000 a month). Remote or ${"Pune"}.\nWork on our ${c.summary.toLowerCase().replace(/\.$/, "")}.\nSend your resume to careers@${c.domain}`,
      extracted: null,
    },
  };
}

const LEADS: Lead[] = [
  ...COS.slice(0, 4).map((c): Lead => ({
    id: "j" + c.id, status: "done", error: null, source_ref: null, first_seen_at: ago(c.created), posted_age_hours: c.draftAge - 0.3,
    title: c.role, company_name: c.company, location: "Pune / Remote", decision: "keep", reasons: [], flags: c.calls,
    overridden: false, rank: 8, track_key: "sde", verification: c.calls.length ? "flag" : "pass",
    application_id: c.id, application_status: c.status,
  })),
  { id: "jx1", status: "done", error: null, source_ref: null, first_seen_at: ago(6), posted_age_hours: 4, title: "Python Developer Intern",
    company_name: "SkillSprint Academy", location: "Online", decision: "drop",
    reasons: ["Asks candidates to pay a registration fee", "Certificates offered as the main benefit"], flags: [],
    overridden: false, rank: null, track_key: null, verification: null, application_id: null, application_status: null },
  { id: "jx2", status: "done", error: null, source_ref: null, first_seen_at: ago(30), posted_age_hours: 50, title: "Backend Intern",
    company_name: "TalentBridge Staffing", location: "Hyderabad", decision: "drop",
    reasons: ["Posted by a recruiter, not the company. No intermediary post has ever converted."], flags: [],
    overridden: false, rank: null, track_key: null, verification: null, application_id: null, application_status: null },
];

const FACTBANK: FactBank = {
  items: [
    { id: "i1", key: "queuekit", kind: "project", name: "QueueKit", tagline: "Lightweight Job Queue", period: "Jan 2026 – Apr 2026",
      stack: "Go, PostgreSQL, Docker, GitHub Actions", stack_label: "Stack", links: [], confirmed: true, sort: 0, bullets: [
        { id: "b1", item_id: "i1", text: "Built a Postgres-backed job queue for a college fest app that lost registration emails whenever its mail provider timed out during peak signups.", confirmed: true, has_metric: false, sort: 0 },
        { id: "b2", item_id: "i1", text: "Used SKIP LOCKED row claiming so four workers process jobs without double delivery, sustaining 300 jobs per second in a local load test.", confirmed: true, has_metric: true, sort: 1 },
        { id: "b3", item_id: "i1", text: "Added exponential retry with a dead-letter table, cutting lost emails in the 2026 fest registration week from about 40 to zero.", confirmed: false, has_metric: true, sort: 2 },
      ] },
    { id: "i2", key: "campusbites", kind: "project", name: "CampusBites", tagline: "Canteen Pre-order API", period: "Aug 2025 – Nov 2025",
      stack: "Node.js, Express, MongoDB, Redis", stack_label: "Stack", links: [], confirmed: true, sort: 1, bullets: [
        { id: "b4", item_id: "i2", text: "Replaced the paper token system at the hostel canteen with a pre-order API, so students stop queueing through the lunch rush.", confirmed: true, has_metric: false, sort: 0 },
        { id: "b5", item_id: "i2", text: "Cached the daily menu in Redis and served 1,200 orders in the first month with p95 response times under 120 ms.", confirmed: true, has_metric: true, sort: 1 },
        { id: "b6", item_id: "i2", text: "Wrote 35 integration tests covering ordering, cancellation and stock limits, running on every push through GitHub Actions.", confirmed: true, has_metric: true, sort: 2 },
      ] },
  ],
  sections: [
    { id: "s1", key: "awards", heading: "Awards & Certifications", entries: [
      { id: "en1", lead: null, text: "Finalist, inter-college hackathon of 120 teams, 2025", tracks: null, confirmed: true }] },
    { id: "s2", key: "roles", heading: "Other Roles & Responsibilities", entries: [
      { id: "en2", lead: "Web Team Lead, Coding Club (Aug 2024 – May 2025)", text: " — ran weekly backend workshops for 40 juniors.", tracks: null, confirmed: true }] },
  ],
  education: [{ id: "ed1", institution: "Deccan Institute of Technology", degree: "B.Tech, Information Technology",
    meta: "Pune, Maharashtra, Aug 2023 – May 2027", result: "CGPA: 8.1 / 10", lines: [], confirmed: true }],
  facts: ["Go", "PostgreSQL", "Node.js", "Express", "Redis", "MongoDB", "Docker", "GitHub Actions", "Python", "Kubernetes"].map((t, i) => ({
    id: "sk" + i, kind: "skill", text: t, source: "upload", confirmed_at: t === "Kubernetes" ? null : ago(48),
    evidence_items: t === "Python" ? [] : ["queuekit"],
  })),
};

const TRACKS: Track[] = [{
  id: "t1", key: "sde", label: "Backend / SDE", title_line: "Backend Developer · B.Tech Information Technology, 2027",
  summary: "Final-year IT student who builds backend services that keep working under load: a job queue that stopped a fest app from losing emails, and a canteen ordering API used daily in the hostel.",
  left_sections: [{ heading: "Projects", item_keys: ["queuekit", "campusbites"] }],
  skills: [{ label: "Languages", items: "Go, Python" }, { label: "Backend", items: "Node.js, Express, Redis" }, { label: "Databases", items: "PostgreSQL, MongoDB" }],
  scale: 1.04, approved: true, baseline: { id: "rbase", scale: 1.04, ats_score: 82.5 },
}];

let roles: RoleOption[] = [
  { id: "o1", field: "backend", role: "Backend Developer Intern", fit: "strong", why: "QueueKit and CampusBites are both backend services you built and ran under real load.", evidence_item_keys: ["queuekit", "campusbites"], gaps: [], desired: true, selected: true, pool_jobs: 14, watched: true },
  { id: "o2", field: "fullstack", role: "Full-stack Developer Intern", fit: "good", why: "CampusBites shipped an API students used daily; you led the coding club's web team.", evidence_item_keys: ["campusbites"], gaps: ["no frontend project of your own"], desired: false, selected: true, pool_jobs: 9, watched: true },
  { id: "o3", field: "devops", role: "DevOps Intern", fit: "good", why: "QueueKit runs in Docker with a GitHub Actions pipeline you set up.", evidence_item_keys: ["queuekit"], gaps: ["no cloud deployment experience yet"], desired: false, selected: false, pool_jobs: 0, watched: false },
  { id: "o4", field: "data_engineering", role: "Data Engineer Intern", fit: "stretch", why: "You know PostgreSQL well, but no project moves or models data at scale.", evidence_item_keys: [], gaps: ["no pipeline or warehouse project", "no Spark or Airflow"], desired: false, selected: false, pool_jobs: 3, watched: false },
  { id: "o5", field: "ai_ml", role: "ML Engineer Intern", fit: "stretch", why: "You asked for ML roles, but none of your confirmed work involves a model yet.", evidence_item_keys: [], gaps: ["no ML project", "no Python data stack"], desired: true, selected: false, pool_jobs: 21, watched: true },
];

function route(method: string, path: string, body: unknown): unknown {
  const p = path.split("?")[0];
  if (method === "GET") {
    if (p === "/me") return me;
    if (p === "/today") {
      const apps = COS.map(application);
      return {
        deadlines: [{ id: "e2", type: "interview", deadline_at: ahead(26), summary: "30-minute call with the CTO", application_id: "a4",
          company_name: "Tessera Analytics", role_title: "Backend Engineer Intern" }],
        drafts: apps.filter((a) => ["drafted", "needs_review"].includes(a.status)).sort((x, y) => (x.age_at_draft_hours ?? 0) - (y.age_at_draft_hours ?? 0)),
        decisions: LEADS.filter((l) => l.decision === "drop"),
        gaps: [{ id: "b1", text: FACTBANK.items[0].bullets[0].text, item_name: "QueueKit" },
               { id: "b4", text: FACTBANK.items[1].bullets[0].text, item_name: "CampusBites" }],
        processing: 0,
      };
    }
    if (p === "/applications") return COS.map(application);
    if (p.startsWith("/applications/")) return detail(p.split("/")[2]);
    if (p === "/leads") return LEADS;
    if (p === "/factbank") return FACTBANK;
    if (p === "/tracks") return TRACKS;
    if (p === "/onboarding/roles") return roles;
    if (p === "/onboarding/interview") return [
      { role: "assistant", content: "QueueKit took lost emails from about 40 to zero. How many students registered during that fest week?" },
      { role: "user", content: "About 2,300 registrations, from the fest dashboard." },
      { role: "assistant", content: "Did anyone other than you use CampusBites after launch, for example the canteen staff?" },
    ];
    if (p === "/onboarding/evidence") return FACTBANK.facts.filter((f) => f.confirmed_at).map((f) => ({
      fact_id: f.id, skill: f.text, backed_by: f.evidence_items, backed: f.evidence_items.length > 0 }));
    if (p === "/usage") return {
      steps: [
        { step: "s1_extract", calls: 8, input_tokens: 21400, output_tokens: 6100, cache_read_tokens: 9600, cost_usd: 0.0052, avg_latency_ms: 2900 },
        { step: "s5_select", calls: 6, input_tokens: 38200, output_tokens: 4800, cache_read_tokens: 22000, cost_usd: 0.1244, avg_latency_ms: 6100 },
        { step: "s7_draft", calls: 7, input_tokens: 30100, output_tokens: 5900, cache_read_tokens: 18000, cost_usd: 0.1191, avg_latency_ms: 7400 },
      ],
      per_application: { avg_cost_per_application: 0.0414, applications: 6 }, per_lead: { avg_cost_per_lead: 0.0311, leads: 8 },
      total: { cost_usd: 0.2487 },
    };
  }
  if (p === "/onboarding/roles" && method === "POST") {
    return { summary: "You are strongest at backend services that have to keep running under load. Full-stack and DevOps roles are within reach; ML would need a project first.", options: roles };
  }
  if (p === "/onboarding/roles/select") {
    const b = body as { mode: string; option_ids: string[] };
    roles = roles.map((o) => ({ ...o, selected: b.mode === "mix" ? o.fit !== "stretch" : b.option_ids.includes(o.id),
      watched: o.watched || (b.mode === "mix" ? o.fit !== "stretch" : b.option_ids.includes(o.id)) }));
    return roles;
  }
  if (p.endsWith("/link") && method === "POST") {
    const rid = p.split("/")[2];
    links = { ...links, [rid]: { token: "demo" + rid, url: `http://localhost:8000/r/demo${rid}`, opens: 0, last_opened_at: null, created_at: new Date().toISOString() } };
    return links[rid];
  }
  if (p.endsWith("/link") && method === "DELETE") {
    const rid = p.split("/")[2];
    const rest = { ...links };
    delete rest[rid];
    links = rest;
    return { ok: true };
  }
  if (p === "/onboarding/interview" && method === "POST") return { question: "What did the canteen staff change after CampusBites launched?", done: false };
  if (p === "/leads" && method === "POST") return { job_id: "jdemo", duplicate: false };
  if (p.startsWith("/applications/") && method === "PATCH") {
    const id = p.split("/")[2];
    const c = COS.find((x) => x.id === id);
    const st = (body as { status?: string }).status;
    if (c && st) { c.status = st; if (st === "sent" && c.sentAt === undefined) c.sentAt = 0; }
    return { ok: true };
  }
  return { ok: true };
}

export async function demoRequest<T>(method: string, path: string, body?: unknown): Promise<T> {
  await new Promise((r) => setTimeout(r, 120));
  return structuredClone(route(method, path, body)) as T;
}

export async function demoBlob(): Promise<Blob> {
  return (await fetch("/demo/resume_Aarav_Mehta.pdf")).blob();
}
