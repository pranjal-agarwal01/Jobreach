import type { Bucket, ContactContext, Opportunity } from "./types";

export const BUCKET: Record<Bucket, { label: string; short: string; blurb: string; tone: "ok" | "accent" | "warn" }> = {
  strong: { label: "Strong matches", short: "Strong match", tone: "ok",
    blurb: "Your own work shows what they ask for." },
  good: { label: "Good matches", short: "Good match", tone: "accent",
    blurb: "Most of what they ask for, with a gap or two." },
  gaps: { label: "Worth a look, with gaps", short: "With gaps", tone: "warn",
    blurb: "Stretch roles. If you write, the letter names each gap honestly instead of hiding it." },
};

export const WHERE_SHORT: Record<ContactContext, string> = {
  post_apply: "from the post", careers_page: "from their site", site_generic: "general inbox only",
};

const lakh = (n: number) => (n / 100000).toFixed(n % 100000 ? 1 : 0).replace(/\.0$/, "");

function money(n: number, cur: string | null): string {
  if (cur && cur !== "INR") return `${cur} ${n.toLocaleString("en-IN")}`;
  if (n >= 1000) return `₹${Math.round(n / 1000)}k`;
  return `₹${n}`;
}

/** "₹20k a month", "₹15k–25k a month", "8–12 LPA". Null when the post states no figure. */
export function payLabel(o: Pick<Opportunity, "pay_min" | "pay_max" | "pay_currency" | "pay_period">): string | null {
  if (o.pay_min == null && o.pay_max == null) return null;
  const lo = Number(o.pay_min ?? o.pay_max), hi = Number(o.pay_max ?? o.pay_min);
  if (o.pay_period === "year" && (!o.pay_currency || o.pay_currency === "INR")) {
    return lo === hi ? `${lakh(lo)} LPA` : `${lakh(lo)}–${lakh(hi)} LPA`;
  }
  const range = lo === hi ? money(lo, o.pay_currency) : `${money(lo, o.pay_currency)}–${money(hi, o.pay_currency).replace("₹", "")}`;
  return `${range}${o.pay_period === "month" ? " a month" : o.pay_period === "year" ? " a year" : o.pay_period === "total" ? " in total" : ""}`;
}

export function placeLabel(o: Pick<Opportunity, "work_mode" | "city">): string | null {
  if (o.work_mode === "remote") return "Remote";
  if (o.work_mode === "hybrid") return o.city ? `Hybrid, ${o.city}` : "Hybrid";
  if (o.work_mode === "onsite") return o.city ? `${o.city}, onsite` : "Onsite";
  return o.city;
}

export function kindLabel(o: Pick<Opportunity, "employment_type">): string | null {
  return { internship: "Internship", full_time: "Full-time", both: "Internship or full-time" }[o.employment_type ?? ""] ?? null;
}

export function experienceLabel(o: Pick<Opportunity, "exp_min" | "exp_max">): string | null {
  const lo = o.exp_min == null ? null : Number(o.exp_min), hi = o.exp_max == null ? null : Number(o.exp_max);
  if (lo == null && hi == null) return null;
  if (lo != null && hi != null) return lo === hi ? (lo === 0 ? "Freshers" : `${lo} years`) : `${lo}–${hi} years`;
  return lo != null ? `${lo}+ years` : `Up to ${hi} years`;
}

/** Who the letter would go to, and where that address was published. */
export function contactLine(o: Pick<Opportunity, "route" | "apply_to" | "contact_email" | "contact_name" |
  "contact_role" | "contact_context">): { who: string; where: string | null; weak: boolean } {
  if (o.route === "portal") return { who: "Apply on their portal", where: "no published address", weak: false };
  if (!o.contact_email) return { who: "No route to apply", where: null, weak: true };
  const who = o.contact_name ? `Email ${o.contact_name}${o.contact_role ? `, ${o.contact_role}` : ""}` : `Email ${o.contact_email}`;
  return { who, where: o.contact_context ? WHERE_SHORT[o.contact_context] : null, weak: o.contact_context === "site_generic" };
}

export const preparing = (o: Pick<Opportunity, "prepare_status">) =>
  o.prepare_status === "queued" || o.prepare_status === "running";
