// Role families, as S1 extracts them from a post and matching compares them. Mirrors
// FAMILIES in backend/app/taxonomy.py (keys and labels); keep the two in step.
export const FIELDS: [string, string][] = [
  ["sde", "Software engineering"], ["backend", "Backend"], ["frontend", "Frontend"], ["fullstack", "Full stack"],
  ["mobile", "Mobile"], ["ai_ml", "AI and ML"], ["cv", "Computer vision"], ["data_analytics", "Data analytics"],
  ["data_engineering", "Data engineering"], ["devops", "DevOps and cloud"], ["qa", "QA and testing"],
  ["embedded", "Embedded"], ["security", "Security"], ["design", "Design"], ["product", "Product"],
  ["business", "Business"], ["marketing", "Marketing"], ["operations", "Operations"],
];

export const FIELD_LABEL: Record<string, string> = Object.fromEntries(FIELDS);
