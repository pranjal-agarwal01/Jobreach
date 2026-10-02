import { FIELD_LABEL } from "./fields";
import type { Fit, Stage } from "./types";

export const STAGES: { key: Stage; label: string; hint: string }[] = [
  { key: "student", label: "Student", hint: "Looking for internships" },
  { key: "graduate", label: "Recent graduate", hint: "After a first full-time job" },
  { key: "experienced", label: "Experienced", hint: "Working, and ready to switch" },
];

export const FIT_LABEL: Record<Fit, string> = { strong: "Strong fit", good: "Good fit", stretch: "Stretch" };
export const FIT_TONE: Record<Fit, "ok" | "accent" | "warn"> = { strong: "ok", good: "accent", stretch: "warn" };

/** "Backend" -> "backend", but "AI and ML" and "DevOps and cloud" keep their capitals. */
function inSentence(label: string): string {
  return label.split(" ").map((w, i) =>
    i === 0 && w.length > 1 && w[1] === w[1].toLowerCase() ? w[0].toLowerCase() + w.slice(1) : w).join(" ");
}

export function listOf(parts: string[]): string {
  if (parts.length <= 1) return parts.join("");
  return `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}`;
}

/** How Jobreach describes the user back to them: "You have 3 years of experience and you're
 *  targeting software engineering and AI and ML roles." */
export function describe(stage: Stage | null, years: number | null, families: string[]): string {
  const roles = listOf(families.map((f) => inSentence(FIELD_LABEL[f] ?? f)));
  if (stage === "student") return `You're a student looking for ${roles} internships.`;
  if (stage === "graduate") return `You're a recent graduate looking for ${roles} roles.`;
  const y = Math.floor(years ?? 0);
  if (y < 1) return `You're looking for ${roles} roles.`;
  return `You have ${y} year${y === 1 ? "" : "s"} of experience and you're targeting ${roles} roles.`;
}
