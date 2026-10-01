// Everything the landing page shows is made up: Rohan Das is synthetic test profile 05
// (backend/tests/fixtures/profiles), and the companies are fictional. Every number in his
// lines comes from that profile, so the page practises what it promises: nothing invented.

export interface Bullet { id: string; text: string }
export interface Project { id: string; name: string; tagline: string; stack: string; bullets: Bullet[] }

export const PROJECTS: Record<string, Project> = {
  pixelforge: {
    id: "pixelforge", name: "PixelForge", tagline: "Image Processing API",
    stack: "Python, FastAPI, Celery, Redis, Docker",
    bullets: [
      { id: "pf1", text: "Built an image-processing API for resizing and watermarking uploads, so small shops stop editing product photos by hand." },
      { id: "pf2", text: "Moved processing to a Celery worker pool, handling about 60 images per second on a four-core machine without blocking requests." },
      { id: "pf4", text: "Secured the API with key-based auth and per-key rate limits, returning clear 429 responses with retry-after headers." },
    ],
  },
  tutorlink: {
    id: "tutorlink", name: "TutorLink", tagline: "Tutoring Marketplace",
    stack: "Next.js, TypeScript, PostgreSQL, Prisma, Tailwind CSS",
    bullets: [
      { id: "tl1", text: "Built a marketplace matching college tutors with school students, replacing word-of-mouth tutoring that left most tutors underbooked." },
      { id: "tl2", text: "Rendered listings with Next.js server components over PostgreSQL through Prisma, keeping the client bundle small on low-end phones." },
      { id: "tl3", text: "Reached a Lighthouse mobile performance score of 96 after optimising images and splitting the bundle by route." },
      { id: "tl4", text: "Prevented double-booked slots with a database exclusion constraint rather than application checks that race under load." },
    ],
  },
  splitsy: {
    id: "splitsy", name: "Splitsy", tagline: "Shared Expense Tracker",
    stack: "React, TypeScript, Node.js, Express, MongoDB",
    bullets: [
      { id: "sp1", text: "Built an expense-splitting app for hostel roommates, who were tracking shared costs in a group chat and losing track of who owed whom." },
      { id: "sp2", text: "Settled each group's debts in at most n-1 payments with a greedy min-cash-flow algorithm instead of pairwise repayments." },
      { id: "sp3", text: "Grew to 140 students across three hostels in the first semester, spread entirely by roommates inviting each other." },
      { id: "sp4", text: "Used optimistic UI updates with server reconciliation, so expenses added offline sync cleanly once the hostel Wi-Fi returns." },
    ],
  },
  devfolio: {
    id: "devfolio", name: "Devfolio Kit", tagline: "Portfolio Site Generator",
    stack: "React, Vite, Tailwind CSS",
    bullets: [
      { id: "dk1", text: "Built a generator that turns one JSON file into a static portfolio site, for students who want a portfolio without writing CSS." },
      { id: "dk2", text: "Designed six themes in Tailwind CSS that meet accessible colour-contrast ratios in both light and dark modes." },
      { id: "dk3", text: "Reached 210 GitHub stars, with issues and theme requests arriving from students at other colleges." },
    ],
  },
};

export interface Opening {
  id: string;
  company: string;
  role: string;
  hoursOld: number;
  asks: string[];
  baseline: string;
  titleLine: string;
  items: { project: string; bullets: string[] }[];
  skills: string[];
  changes: string[];
}

/** Three openings, three tailored resumes, all cut from the same record. */
export const OPENINGS: Opening[] = [
  {
    id: "kitebox", company: "Kitebox Labs", role: "Backend Developer Intern", hoursOld: 2,
    asks: ["Python", "FastAPI", "Redis", "PostgreSQL"],
    baseline: "Backend",
    titleLine: "Backend Developer, B.Tech Computer Science 2027",
    items: [
      { project: "pixelforge", bullets: ["pf2", "pf1", "pf4"] },
      { project: "tutorlink", bullets: ["tl4", "tl2"] },
      { project: "splitsy", bullets: ["sp2"] },
    ],
    skills: ["Python", "FastAPI", "Redis", "PostgreSQL", "Celery", "Docker"],
    changes: [
      "Started from his Backend resume",
      "PixelForge leads: FastAPI and Redis, like the post asks",
      "The double-booking fix from TutorLink moved up for PostgreSQL",
      "Devfolio Kit left out, so the page stays one page",
    ],
  },
  {
    id: "ledgerleaf", company: "Ledgerleaf", role: "Frontend Engineer Intern", hoursOld: 5,
    asks: ["React", "TypeScript", "Next.js", "accessible"],
    baseline: "Frontend",
    titleLine: "Frontend Developer, B.Tech Computer Science 2027",
    items: [
      { project: "tutorlink", bullets: ["tl3", "tl2"] },
      { project: "devfolio", bullets: ["dk2", "dk3"] },
      { project: "splitsy", bullets: ["sp4", "sp1"] },
    ],
    skills: ["React", "Next.js", "TypeScript", "Tailwind CSS", "Accessibility", "Lighthouse"],
    changes: [
      "Started from his Frontend resume",
      "TutorLink leads with its Lighthouse score of 96",
      "Devfolio Kit's accessible themes moved up",
      "PixelForge left out: the post asks for no backend work",
    ],
  },
  {
    id: "pinewheel", company: "Pinewheel Health", role: "Full-stack Developer Intern", hoursOld: 9,
    asks: ["Next.js", "Node.js", "PostgreSQL", "TypeScript"],
    baseline: "Full stack",
    titleLine: "Full-Stack Developer, B.Tech Computer Science 2027",
    items: [
      { project: "tutorlink", bullets: ["tl1", "tl2"] },
      { project: "splitsy", bullets: ["sp1", "sp3"] },
      { project: "pixelforge", bullets: ["pf1"] },
    ],
    skills: ["TypeScript", "Next.js", "Node.js", "PostgreSQL", "Prisma", "Docker"],
    changes: [
      "Started from his Full-stack resume",
      "TutorLink leads: Next.js and PostgreSQL, end to end",
      "Splitsy's 140 users kept as proof people use his work",
      "Devfolio Kit left out, so the page stays one page",
    ],
  },
];

export const ROLE_FAMILIES = [
  "Backend", "Frontend", "Full stack", "Software engineering", "AI and ML", "Data analytics",
  "Data engineering", "DevOps and cloud", "Mobile", "QA and testing", "Embedded", "Security",
  "Product design", "Product management",
];
