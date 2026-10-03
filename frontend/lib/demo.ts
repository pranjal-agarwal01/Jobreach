// Demo mode: every screen filled with a made-up student (the synthetic "Aarav Mehta" test
// profile) and fictional companies on .example domains, so the signed-in UI can be reviewed
// without an account. Development builds only; turned on at /demo and off from the banner.
import type {
  AppDetail, Application, Build, ContactCandidate, FactBank, IntakeKey, Lead, Me, Opportunity, OpportunityDetail, ResumeLink,
  Review, Today, Track,
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

// A pretend Gmail connection. Kept in the browser because connecting reloads the page.
const GMAIL_KEY = "jobreach-demo-gmail";
function gmailConnected(): boolean {
  try { return typeof window !== "undefined" && window.localStorage.getItem(GMAIL_KEY) === "1"; } catch { return false; }
}
function setGmailConnected(on: boolean) {
  try { if (on) window.localStorage.setItem(GMAIL_KEY, "1"); else window.localStorage.removeItem(GMAIL_KEY); } catch { /* private window */ }
}
const DEMO_GMAIL = "aarav.mehta@example.com";
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
    career_stage: "student", experience_years: 0, experience_band: "intern", portfolio_url: null,
    linkedin_url: "https://linkedin.com/in/aarav-mehta-example",
    build: { status: "done", step: "done", kept: 21, left_out: 2, suggestions: [{ family: "devops", label: "DevOps and cloud",
      why: "QueueKit runs in Docker with a GitHub Actions pipeline you set up, and CampusBites caches its menu in Redis." }] },
  },
  preferences: {
    role_types: ["backend", "sde", "fullstack"], open_to: ["internship"], locations: ["Pune", "Bengaluru", "Remote"],
    remote_ok: true, onsite_ok: true, hybrid_ok: true, stipend_floor: 10000, currency: "INR",
    unpaid_remote_policy: "draft_with_floor", unpaid_onsite_policy: "drop", excluded_company_types: ["big_tech"],
    excluded_companies: [], freshness_ceiling_hours: 72, duration_flex: "Flexible on duration",
    start_date: "Immediately", signature_html: null, desired_roles: ["Backend Developer Intern"],
    target_roles: ["Backend Developer Intern"], target_families: ["backend", "fullstack"], salary_floor: null,
    notice_period: null,
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
    in_gmail: gmailConnected() && c.route === "email" && c.status === "drafted",
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
    ...(gmailConnected() && c.status === "drafted"
      ? { gmail_draft_id: "r-demo-" + c.id, gmail_message_id: "demo" + c.id, gmail_drafted_at: ago(0.2), gmail_error: null,
          gmail_link: "https://mail.google.com/mail/u/0/#drafts" }
      : { gmail_draft_id: null, gmail_message_id: null, gmail_drafted_at: null, gmail_error: null, gmail_link: null }),
  };
}

let intakeKeys: IntakeKey[] = [{ id: "k1", name: "LinkedIn agent", prefix: "jri_4kTq9xWm", created_at: ago(30),
  last_used_at: ago(2) }];

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
    match: { id: "m" + c.id, score: 81, bucket: "strong", why: [
      "Go, PostgreSQL and Docker: used in QueueKit", "Backend is one of your targets; your Backend resume is a strong fit",
      "An internship, and you're a student"], gaps: c.id === "a2" ? ["Asks for React"] : [] },
    contact: c.route === "email" ? { email: c.status === "needs_review" ? "neha.iyer@gmail.com" : `careers@${c.domain}`,
      person_name: c.poster, person_role: c.poster ? "Founder" : null, context: "post_apply", source_url: null,
      evidence: `Send your resume to careers@${c.domain}`, where: "given in the post for applying" } : null,
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
    application_id: c.id, application_status: c.status, match_id: "m" + c.id, score: 81, bucket: "strong",
    prepare_status: "done", prepare_error: null, source: c.id === "a2" ? "agent" : "paste",
    found_by: c.id === "a2" ? "agent: posts: full stack intern, past 24 hours" : null,
  })),
  { id: "jx1", status: "done", error: null, source_ref: null, first_seen_at: ago(6), posted_age_hours: 4, title: "Python Developer Intern",
    company_name: "SkillSprint Academy", location: "Online", decision: "drop",
    reasons: ["Asks candidates to pay a registration fee", "Certificates offered as the main benefit"], flags: [],
    overridden: false, rank: null, track_key: null, verification: null, application_id: null, application_status: null,
    match_id: "mx1", score: null, bucket: null, prepare_status: null, prepare_error: null, source: "paste", found_by: null },
  { id: "jx2", status: "done", error: null, source_ref: null, first_seen_at: ago(30), posted_age_hours: 50, title: "Backend Intern",
    company_name: "TalentBridge Staffing", location: "Hyderabad", decision: "drop",
    reasons: ["Posted by a recruiter, not the company. No intermediary post has ever converted."], flags: [],
    overridden: false, rank: null, track_key: null, verification: null, application_id: null, application_status: null,
    match_id: "mx2", score: null, bucket: null, prepare_status: null, prepare_error: null, source: "agent",
    found_by: "agent: posts: backend intern hyderabad, past 24 hours" },
];

const FACTBANK: FactBank = {
  items: [
    { id: "i1", key: "queuekit", kind: "project", name: "QueueKit", tagline: "Lightweight Job Queue", period: "Jan 2026 – Apr 2026",
      stack: "Go, PostgreSQL, Docker, GitHub Actions", stack_label: "Stack", links: [], confirmed: true, sort: 0, bullets: [
        { id: "b1", item_id: "i1", text: "Built a Postgres-backed job queue for a college fest app that lost registration emails whenever its mail provider timed out during peak signups.", confirmed: true, has_metric: false, sort: 0 },
        { id: "b2", item_id: "i1", text: "Used SKIP LOCKED row claiming so four workers process jobs without double delivery, sustaining 300 jobs per second in a local load test.", confirmed: true, has_metric: true, sort: 1 },
        { id: "b3", item_id: "i1", text: "Added exponential retry with a dead-letter table, cutting lost emails in the 2026 fest registration week from about 40 to zero.", confirmed: false, has_metric: true, sort: 2,
          provenance: { ok: false, reason: "The number 40 is not in anything you gave us" } },
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
    provenance: t === "Kubernetes" ? { ok: false, reason: "Kubernetes is not mentioned in anything you gave us" } : { ok: true, reason: null },
  })),
};

const TRACKS: Track[] = [
  {
    id: "t1", key: "backend", label: "Backend", role_family: "backend", fit: "strong",
    fit_why: "QueueKit and CampusBites are both backend services you built and ran under real load.", gaps: ["no cloud deployment yet"],
    title_line: "Backend Developer · B.Tech Information Technology, 2027",
    summary: "Final-year IT student who builds backend services that keep working under load: a job queue that stopped a fest app from losing emails, and a canteen ordering API used daily in the hostel.",
    left_sections: [{ heading: "Projects", item_keys: ["queuekit", "campusbites"] }],
    skills: [{ label: "Languages", items: "Go, Python" }, { label: "Backend", items: "Node.js, Express, Redis" }, { label: "Databases", items: "PostgreSQL, MongoDB" }],
    scale: 1.04, approved: true, baseline: { id: "rbase", scale: 1.04, ats_score: 82.5 },
  },
  {
    id: "t2", key: "fullstack", label: "Full stack", role_family: "fullstack", fit: "good",
    fit_why: "CampusBites is a full product students used daily, but there is no frontend project of your own yet.", gaps: ["no React or frontend project"],
    title_line: "Full-Stack Developer · B.Tech Information Technology, 2027",
    summary: "Final-year IT student who ships working products: a canteen pre-order service used daily in the hostel, and the job queue behind a college fest's registrations.",
    left_sections: [{ heading: "Projects", item_keys: ["campusbites", "queuekit"] }],
    skills: [{ label: "Languages", items: "Go, Python" }, { label: "Web", items: "Node.js, Express" }, { label: "Data", items: "PostgreSQL, MongoDB, Redis" }],
    scale: 1.06, approved: true, baseline: { id: "rbase2", scale: 1.06, ats_score: 80.1 },
  },
];

// The onboarding build, played forward a step each time the building screen asks.
let buildTicks = 0;
const BUILD_STEPS: NonNullable<Build["step"]>[] = ["reading", "reading", "checking", "checking", "writing", "writing", "writing", "rendering", "rendering"];

function review(): Review {
  return {
    profile: { name: me.profile.name, career_stage: me.profile.career_stage, experience_years: me.profile.experience_years,
      experience_band: me.profile.experience_band, build: me.profile.build, onboarding_step: "review",
      grad_date: me.profile.grad_date, batch_year: me.profile.batch_year },
    preferences: { target_families: me.preferences.target_families, desired_roles: me.preferences.desired_roles },
    item_names: Object.fromEntries(FACTBANK.items.map((i) => [i.key, i.name])),
    counts: { items: 2, bullets: 5, skills: 9 },
    tracks: TRACKS,
    left_out: [
      { kind: "bullet", id: "b3", text: FACTBANK.items[0].bullets[2].text, context: "QueueKit", reason: "The number 40 is not in anything you gave us" },
      { kind: "skill", id: "sk9", text: "Kubernetes", context: null, reason: "Kubernetes is not mentioned in anything you gave us" },
    ],
    suggestions: me.profile.build.suggestions ?? [],
  };
}


// ------------------------------------------------------------------ openings scored for Aarav

interface Opp { id: string; company: string; domain: string; title: string; family: string; bucket: Opportunity["bucket"];
  score: number; age: number; mode: Opportunity["work_mode"]; city: string | null; kind: string;
  pay: [number, number] | null; must: string[]; nice: string[]; why: string[]; gaps: string[];
  contact: Omit<ContactCandidate, "id" | "chosen" | "where" | "is_generic" | "domain_matches" | "confidence"> | null;
  portal?: string; flags?: string[]; summary: string; post: string; prepare?: Opportunity["prepare_status"] }

const WHERE = { post_apply: "given in the post for applying", careers_page: "published on the company's own site as a hiring address",
  site_generic: "the company's general inbox; no hiring address is published" } as const;

const OPPS: Opp[] = [
  { id: "o1", company: "Porchlight", domain: "porchlight.example", title: "Backend Developer Intern", family: "backend",
    bucket: "strong", score: 88, age: 2, mode: "hybrid", city: "Pune", kind: "internship", pay: [20000, 25000],
    must: ["Go or Node.js", "PostgreSQL", "Docker"], nice: ["Redis"],
    why: ["PostgreSQL and Docker: used in QueueKit", "Redis: used in CampusBites", "Backend is one of your targets; your Backend resume is a strong fit",
      "An internship, and you're a student", "Posted 2 hours ago", "Email to Ira Menon (CTO), given in the post for applying"], gaps: [],
    contact: { email: "ira@porchlight.example", person_name: "Ira Menon", person_role: "CTO", context: "post_apply", source_url: null,
      evidence: "Interns: send your resume and one thing you built to me, Ira Menon (CTO), at ira@porchlight.example." },
    summary: "Builds visitor and delivery management for gated housing societies.",
    post: "Ira Menon\nCTO at Porchlight\n2h\n\nWe're hiring a Backend Developer Intern (6 months, Rs 20-25k a month), hybrid in Pune.\nYou'll work on the APIs behind our gate app: Go or Node.js, PostgreSQL, Docker. Redis is a plus.\n\nInterns: send your resume and one thing you built to me, Ira Menon (CTO), at ira@porchlight.example." },
  { id: "o2", company: "Saltpan Studio", domain: "saltpan.example", title: "Backend Engineer Intern", family: "backend",
    bucket: "strong", score: 76, age: 9, mode: "remote", city: null, kind: "internship", pay: [30000, 30000],
    must: ["Go", "PostgreSQL", "gRPC"], nice: [], prepare: "running",
    why: ["Go and PostgreSQL: used in QueueKit", "Backend is one of your targets; your Backend resume is a strong fit",
      "An internship, and you're a student", "Posted 9 hours ago",
      "Email to the hiring team (jobs@saltpan.example), published on the company's own site as a hiring address"], gaps: ["Asks for gRPC"],
    contact: { email: "jobs@saltpan.example", person_name: null, person_role: null, context: "careers_page", source_url: "https://saltpan.example/careers",
      evidence: "Don't see your role? Write to us at jobs@saltpan.example and tell us what you'd build." },
    summary: "Makes scheduling software for independent physiotherapy clinics.",
    post: "Saltpan Studio is hiring a remote Backend Engineer Intern. Rs 30,000 a month. Go, PostgreSQL and gRPC. DM me if you're interested!\n9h" },
  { id: "o3", company: "Brightloom", domain: "brightloom.example", title: "Full Stack Developer Intern", family: "fullstack",
    bucket: "good", score: 64, age: 20, mode: "onsite", city: "Bengaluru", kind: "internship", pay: [18000, 18000],
    must: ["Node.js", "React", "TypeScript"], nice: [], portal: "https://jobs.brightloom.example/fs-intern",
    why: ["Node.js and Express: used in CampusBites", "Full stack is one of your targets; your Full stack resume is a good fit", "Posted 20 hours ago"],
    gaps: ["Asks for React", "Asks for TypeScript"], contact: null,
    summary: "An online store builder for handloom weavers.",
    post: "Brightloom is hiring Full Stack Developer interns in Bengaluru (onsite, Rs 18,000 a month). Node.js, React, TypeScript.\nApply: https://jobs.brightloom.example/fs-intern\n20h" },
  { id: "o4", company: "Tiffinbox", domain: "tiffinbox.example", title: "Software Developer", family: "sde",
    bucket: "good", score: 55, age: 30, mode: "onsite", city: "Pune", kind: "both", pay: null,
    must: ["Node.js", "MongoDB", "Python"], nice: [],
    why: ["Node.js and MongoDB: used in CampusBites", "Close to your Backend target", "Posted 30 hours ago"],
    gaps: ["No project shows Python yet; it's only on your skills list"],
    contact: { email: "hello@tiffinbox.example", person_name: null, person_role: null, context: "site_generic", source_url: "https://tiffinbox.example",
      evidence: "Say hello: hello@tiffinbox.example" },
    flags: ["Only the company's general inbox (hello@tiffinbox.example) is published; no hiring address"],
    summary: "Home-cooked meal subscriptions for office workers in Pune.",
    post: "We're growing! Tiffinbox is looking for a Software Developer in Pune: interns or freshers (0-1 years). Node.js, MongoDB, Python.\n30h" },
  { id: "o5", company: "Orbitly", domain: "orbitly.example", title: "Platform Engineer Intern", family: "devops",
    bucket: "gaps", score: 42, age: 40, mode: "remote", city: null, kind: "internship", pay: [25000, 25000],
    must: ["Docker", "Kubernetes", "Terraform", "AWS"], nice: [],
    why: ["Docker: used in QueueKit", "Close to your Backend target", "Email to the hiring team (careers@orbitly.example), given in the post for applying"],
    gaps: ["Asks for Kubernetes", "Asks for Terraform", "Asks for AWS"],
    contact: { email: "careers@orbitly.example", person_name: null, person_role: null, context: "post_apply", source_url: null,
      evidence: "Send your CV to careers@orbitly.example with the subject Platform Intern." },
    summary: "Cost dashboards for small teams running on AWS.",
    post: "Orbitly is hiring a remote Platform Engineer Intern (Rs 25,000 a month): Docker, Kubernetes, Terraform, AWS.\nSend your CV to careers@orbitly.example with the subject Platform Intern.\n40h" },
];
const oppState: Record<string, { prepare: Opportunity["prepare_status"]; startedAt?: number; app?: string; dismissed?: boolean }> =
  Object.fromEntries(OPPS.map((o) => [o.id, { prepare: o.prepare ?? null, startedAt: o.prepare ? Date.now() : undefined }]));

/** A letter being prepared in demo mode is ready about eight seconds later. */
function tick() {
  for (const o of OPPS) {
    const st = oppState[o.id];
    if (st.prepare === "running" && st.startedAt && Date.now() - st.startedAt > 8000) {
      const id = "a-" + o.id;
      if (!COS.some((c) => c.id === id)) {
        COS.unshift({ id, company: o.company, domain: o.domain, role: o.title, status: "drafted", route: o.contact ? "email" : "portal",
          draftAge: o.age, created: 0, poster: o.contact?.person_name ?? null, summary: o.summary, calls: o.flags ?? [] });
      }
      st.prepare = "done";
      st.app = id;
    }
  }
}

function opportunity(o: Opp): Opportunity {
  const st = oppState[o.id];
  return {
    id: o.id, job_id: "j" + o.id, score: o.score, bucket: o.bucket, why: o.why, gaps: o.gaps, decision: "keep", reasons: [],
    overridden: false, track_key: o.family === "fullstack" ? "fullstack" : "backend", prepare_status: st.prepare, prepare_error: null,
    seen_at: null, dismissed_at: st.dismissed ? ago(0) : null, route: o.contact ? "email" : "portal",
    apply_to: o.contact?.email ?? o.portal ?? null, flags: o.flags ?? [], title: o.title, company_name: o.company,
    role_family: o.family, employment_type: o.kind, work_mode: o.mode, city: o.city, exp_min: o.kind === "both" ? 0 : null,
    exp_max: o.kind === "both" ? 1 : null, pay_min: o.pay?.[0] ?? null, pay_max: o.pay?.[1] ?? null,
    pay_currency: o.pay ? "INR" : null, pay_period: o.pay ? "month" : null, skills_must: o.must, skills_nice: o.nice,
    // An opening with a portal came from the company's job board through the shared pool.
    source: o.portal ? "greenhouse" : "paste", source_ref: o.portal ?? null, visibility: o.portal ? "public" : "private",
    first_seen_at: ago(o.age), age_hours: o.age,
    domain: o.domain, verification: "pass", contact_email: o.contact?.email ?? null, contact_name: o.contact?.person_name ?? null,
    contact_role: o.contact?.person_role ?? null, contact_context: o.contact?.context ?? null,
    application_id: st.app ?? null, application_status: st.app ? "drafted" : null,
  };
}

function opportunityDetail(id: string): OpportunityDetail {
  const o = OPPS.find((x) => x.id === id) ?? OPPS[0];
  const contacts: ContactCandidate[] = o.contact ? [{ ...o.contact, id: "c" + o.id, chosen: true, where: WHERE[o.contact.context],
    is_generic: !o.contact.person_name, domain_matches: true, confidence: o.contact.context === "post_apply" ? 0.95 : o.contact.context === "careers_page" ? 0.8 : 0.5 }] : [];
  if (o.id === "o1") contacts.push({ id: "c1b", email: "careers@porchlight.example", person_name: null, person_role: null, context: "careers_page",
    source_url: "https://porchlight.example/careers", evidence: "Write to careers@porchlight.example", is_generic: true, domain_matches: true,
    confidence: 0.8, chosen: false, where: WHERE.careers_page });
  return { ...opportunity(o), job: { raw_text: o.post, extracted: null },
    company: { name: o.company, domain: o.domain, verification: "pass", business_summary: o.summary, flags: [] }, contacts };
}

function today(): Today {
  tick();
  const apps = COS.map(application);
  const open = OPPS.map(opportunity).filter((o) => !o.dismissed_at && !o.application_id);
  const busy = Object.values(oppState).filter((s) => s.prepare === "running").length;
  return {
    deadlines: [{ id: "e2", type: "interview", deadline_at: ahead(26), summary: "30-minute call with the CTO", application_id: "a4",
      company_name: "Tessera Analytics", role_title: "Backend Engineer Intern" }],
    ready: apps.filter((a) => ["drafted", "needs_review"].includes(a.status)).sort((x, y) => (x.age_at_draft_hours ?? 0) - (y.age_at_draft_hours ?? 0)),
    groups: { strong: open.filter((o) => o.bucket === "strong"), good: open.filter((o) => o.bucket === "good"),
      gaps: open.filter((o) => o.bucket === "gaps") },
    decisions: LEADS.filter((l) => l.decision === "drop"),
    number_gaps: [{ id: "b1", text: FACTBANK.items[0].bullets[0].text, item_name: "QueueKit" },
      { id: "b4", text: FACTBANK.items[1].bullets[0].text, item_name: "CampusBites" }],
    processing: busy,
    me: { name: me.profile.name, career_stage: me.profile.career_stage, experience_years: me.profile.experience_years,
      experience_band: me.profile.experience_band, target_families: me.preferences.target_families },
  };
}

function route(method: string, path: string, body: unknown): unknown {
  const p = path.split("?")[0];
  if (method === "GET") {
    if (p === "/me") return me;
    if (p === "/today") return today();
    if (p === "/opportunities") {
      tick();
      const all = OPPS.map(opportunity).filter((o) => !o.dismissed_at);
      return { strong: all.filter((o) => o.bucket === "strong"), good: all.filter((o) => o.bucket === "good"),
        gaps: all.filter((o) => o.bucket === "gaps") };
    }
    if (p.startsWith("/opportunities/")) { tick(); return opportunityDetail(p.split("/")[2]); }
    if (p === "/applications") return COS.map(application);
    if (p.startsWith("/applications/")) return detail(p.split("/")[2]);
    if (p === "/leads") return LEADS;
    if (p === "/factbank") return FACTBANK;
    if (p === "/intake/keys") return intakeKeys;
    if (p === "/gmail") return { available: true, connected: gmailConnected(), expired: false,
      email: gmailConnected() ? DEMO_GMAIL : null, connected_at: gmailConnected() ? ago(0.1) : null, unverified: true };
    if (p === "/tracks") return TRACKS;
    if (p === "/onboarding/review") return review();
    if (p === "/onboarding/status") {
      const step = BUILD_STEPS[Math.min(buildTicks++, BUILD_STEPS.length - 1)];
      const done = buildTicks > BUILD_STEPS.length;
      return { step: done ? "review" : "building", build: { status: done ? "done" : "running", step: done ? "done" : step,
        ...(buildTicks > 3 ? { kept: 21, left_out: 2 } : {}) } };
    }
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
  if (p === "/onboarding/start") { buildTicks = 0; return { ok: true, families: ["backend", "fullstack"] }; }
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
  if (p === "/leads" && method === "POST") return { job_id: "jdemo", duplicate: false };
  if (p === "/gmail/connect") {
    setGmailConnected(true);
    const back = (body as { return_to?: string } | undefined)?.return_to ?? "/today";
    return { url: back + "?gmail=connected" };
  }
  if (p === "/gmail" && method === "DELETE") { setGmailConnected(false); return { ok: true }; }
  if (p.endsWith("/gmail-draft")) return { queued: true };
  if (p === "/intake/keys" && method === "POST") {
    const key = "jri_demoOnlyNotARealKey" + Math.random().toString(36).slice(2, 10);
    const row = { id: "k" + (intakeKeys.length + 1), name: (body as { name: string }).name, prefix: key.slice(0, 12),
      created_at: new Date().toISOString(), last_used_at: null };
    intakeKeys = [row, ...intakeKeys];
    return { ...row, key };
  }
  if (p.startsWith("/intake/keys/") && method === "DELETE") {
    intakeKeys = intakeKeys.filter((k) => k.id !== p.split("/")[3]);
    return { ok: true };
  }
  if (p.startsWith("/opportunities/") && p.endsWith("/prepare")) {
    const st = oppState[p.split("/")[2]];
    if (st && !st.app) { st.prepare = "running"; st.startedAt = Date.now(); }
    return st?.app ? { application_id: st.app } : { queued: true };
  }
  if (p.startsWith("/opportunities/") && p.endsWith("/dismiss")) {
    const st = oppState[p.split("/")[2]];
    if (st) st.dismissed = (body as { dismissed?: boolean } | undefined)?.dismissed ?? true;
    return { ok: true };
  }
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
