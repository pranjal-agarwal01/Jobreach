import Link from "next/link";
import { Brand } from "@/components/AppShell";
import { Postmark } from "@/components/ui";
import { GetStarted, Reveal } from "./primitives";

export function FinalCta() {
  return (
    <section className="px-4 pb-10 pt-8 sm:px-6">
      <div className="relative mx-auto max-w-[1320px] overflow-hidden rounded-[34px] bg-inland ring-1 ring-inland-edge">
        <div className="airmail-edge absolute inset-x-0 top-0 h-2.5" />
        {/* Three letters, fanned on the desk: the last one already sent. */}
        <div aria-hidden="true" className="pointer-events-none absolute right-12 top-1/2 hidden h-[300px] w-[400px] -translate-y-1/2 lg:block xl:right-24">
          {[
            { to: "Arvind", r: -9, x: -34, y: 26 },
            { to: "Meher", r: -3, x: -14, y: 10 },
            { to: "Riya", r: 3, x: 0, y: 0 },
          ].map((l, i) => (
            <div key={l.to} className="paper absolute inset-0 overflow-hidden"
              style={{ transform: `translate(${l.x}px, ${l.y}px) rotate(${l.r}deg)` }}>
              <div className="airmail-edge h-2" />
              <div className="px-8 pt-7 font-letter text-[15px] leading-[1.75] text-text-2">
                <p className="font-sans text-xs text-muted">To careers@{["tessera", "ledgerleaf", "kitebox"][i]}.example</p>
                <p className="mt-3 text-text">Hi {l.to},</p>
                <p className="mt-1.5">I saw your post this morning, and the work you describe is the work I have been doing&hellip;</p>
              </div>
              {i === 2 && <Postmark date={new Date().toISOString()} className="absolute bottom-6 right-6 size-24!" />}
            </div>
          ))}
        </div>
        <Reveal className="relative px-7 py-20 sm:px-14 sm:py-28 md:max-w-[62%]">
          <h2 className="text-balance text-[40px] font-bold leading-[1.04] tracking-[-0.035em] sm:text-[60px]">Start with one form.</h2>
          <p className="mt-5 max-w-[40ch] text-[19px] leading-relaxed text-text-2">
            Upload your CV, choose your roles, and see your resumes in a few minutes.
          </p>
          <div className="mt-10"><GetStarted size="lg" /></div>
        </Reveal>
      </div>
    </section>
  );
}

export function Footer() {
  return (
    <footer className="px-4 pb-10 pt-12 sm:px-6">
      <div className="mx-auto flex max-w-[1320px] flex-col gap-8 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <Brand />
          <p className="mt-3 max-w-sm text-[15px] text-muted">Jobreach prepares the letter. You send it.</p>
        </div>
        <nav aria-label="Footer" className="flex flex-wrap gap-x-6 gap-y-2 text-sm font-semibold text-text-2">
          <a href="#how" className="hover:text-text">How it works</a>
          <a href="#promises" className="hover:text-text">Promises</a>
          <a href="#faq" className="hover:text-text">FAQ</a>
          <Link href="/login" className="hover:text-text">Sign in</Link>
        </nav>
      </div>
      <p className="mx-auto mt-10 max-w-[1320px] border-t border-border pt-6 text-[13px] text-muted">&copy; 2026 Jobreach</p>
    </footer>
  );
}
