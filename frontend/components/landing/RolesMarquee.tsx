import { ROLE_FAMILIES } from "./content";

/** The breadth, in one moving line. Pauses on hover; with reduced motion it simply wraps. */
export default function RolesMarquee() {
  return (
    <section aria-label="Roles Jobreach covers" className="border-y border-border/70 bg-surface/40 py-5">
      <div className="mx-auto flex max-w-[1320px] items-center gap-6 px-4 sm:px-6">
        <p className="shrink-0 text-sm font-semibold text-muted">Openings across</p>
        <div className="marquee relative min-w-0 flex-1 overflow-hidden [mask-image:linear-gradient(90deg,transparent,black_6%,black_94%,transparent)]">
          <ul className="marquee-track flex w-max gap-2.5">
            {[...ROLE_FAMILIES, ...ROLE_FAMILIES].map((r, i) => (
              <li key={i} aria-hidden={i >= ROLE_FAMILIES.length || undefined}
                className="whitespace-nowrap rounded-full border border-border bg-surface px-4 py-1.5 text-sm font-semibold text-text-2">
                {r}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
