import type { Metadata } from "next";
import Faq from "@/components/landing/Faq";
import { FinalCta, Footer } from "@/components/landing/FinalCta";
import Hero from "@/components/landing/Hero";
import HowItWorks from "@/components/landing/HowItWorks";
import Lessons from "@/components/landing/Lessons";
import Nav from "@/components/landing/Nav";
import { MotionRoot } from "@/components/landing/primitives";
import Promises from "@/components/landing/Promises";
import RolesMarquee from "@/components/landing/RolesMarquee";
import SharedSearch from "@/components/landing/SharedSearch";
import Stages from "@/components/landing/Stages";
import TailorBench from "@/components/landing/TailorBench";

export const metadata: Metadata = {
  title: "Jobreach: write to founders while the post is still fresh",
  description:
    "Jobreach finds openings that fit you, makes a one-page resume and a letter for each from your own CV, and you press Send.",
  openGraph: {
    title: "Jobreach",
    description: "Openings that fit you, a resume and a letter for each, sent by you.",
    type: "website",
  },
};

/** The public front page: what Jobreach is, shown with a made-up student. No sign-in needed. */
export default function Landing() {
  return (
    <MotionRoot>
      <a href="#main" className="sr-only z-50 rounded-lg bg-surface px-4 py-2 font-semibold focus:not-sr-only focus:fixed focus:left-4 focus:top-4">
        Skip to content
      </a>
      <Nav />
      <main id="main" className="overflow-x-clip">
        <Hero />
        <RolesMarquee />
        <Lessons />
        <HowItWorks />
        <TailorBench />
        <SharedSearch />
        <Stages />
        <Promises />
        <Faq />
        <FinalCta />
      </main>
      <Footer />
    </MotionRoot>
  );
}
