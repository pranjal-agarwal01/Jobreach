// Discipline keys, as S1 extracts them from a post and the S3 filter compares them.
export const FIELDS: [string, string][] = [
  ["sde", "SDE"], ["backend", "Backend"], ["fullstack", "Full-stack"], ["frontend", "Frontend"],
  ["ai_ml", "AI / ML"], ["cv", "Computer vision"], ["data", "Data"], ["devops", "DevOps"],
  ["mobile", "Mobile"], ["embedded", "Embedded"], ["qa", "QA"], ["design", "Design"],
  ["product", "Product"], ["business", "Business / analyst"], ["operations", "Operations"],
  ["marketing", "Marketing"],
];

export const FIELD_LABEL: Record<string, string> = Object.fromEntries(FIELDS);
