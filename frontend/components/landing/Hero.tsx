import HeroDesk from "./HeroDesk";
import { GetStarted } from "./primitives";

export default function Hero() {
  return (
    <section className="relative px-4 pb-16 pt-28 sm:px-6 sm:pt-32 lg:pb-24">
      {/* A soft pool of inland blue behind the desk, nothing more. */}
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
        <div className="absolute -right-[12%] top-[2%] h-[760px] w-[900px] bg-[radial-gradient(closest-side,var(--inland),transparent)]" />
      </div>
      <div className="mx-auto grid max-w-[1320px] items-center gap-14 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)] lg:gap-12">
        <div className="max-w-[660px]">
          <h1 className="text-balance hero-rise text-[40px] font-bold leading-[1.04] tracking-[-0.035em] sm:text-[54px] xl:text-[62px]">
            Write to founders while the post is still fresh.
          </h1>
          <p className="hero-rise mt-6 max-w-[36ch] text-[18px] leading-relaxed text-text-2 sm:text-[20px]" style={{ animationDelay: "120ms" }}>
            Jobreach finds openings that fit you, makes a one-page resume and a letter for each, and you press Send.
          </p>
          <div className="hero-rise mt-9 flex flex-wrap items-center gap-3" style={{ animationDelay: "240ms" }}>
            <GetStarted size="lg" />
            <a href="#how" className="rounded-full px-6 py-3.5 text-[15px] font-semibold text-text-2 ring-1 ring-border-strong transition-colors hover:text-text hover:ring-text-2">
              See how it works
            </a>
          </div>
        </div>
        <div className="hero-rise" style={{ animationDelay: "160ms" }}>
          <HeroDesk />
        </div>
      </div>
    </section>
  );
}
