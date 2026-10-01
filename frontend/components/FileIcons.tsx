const FOLDER = "M3 7a2 2 0 0 1 2-2h4.2a2 2 0 0 1 1.4.6L12 7h7a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z";

export function FolderIcon({ className = "size-10" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={`${className} shrink-0 text-accent`} aria-hidden="true">
      <path fill="currentColor" opacity="0.18" d={FOLDER} />
      <path fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" d={FOLDER} />
    </svg>
  );
}

export function FileIcon({ label, className = "size-9" }: { label: string; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={`${className} shrink-0 text-bad`} aria-hidden="true">
      <path fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"
        d="M6 3h8l4 4v14H6z M14 3v4h4" />
      <text x="12" y="17.5" textAnchor="middle" fontSize="5.5" fontWeight="700" fill="currentColor">{label}</text>
    </svg>
  );
}

export function MailIcon({ className = "size-9" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={`${className} shrink-0 text-accent`} aria-hidden="true">
      <rect x="3" y="5.5" width="18" height="13" rx="2" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <path d="m4 7 8 6 8-6" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  );
}
