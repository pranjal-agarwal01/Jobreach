import { IconChevronDown } from "@/components/icons";

const QA: [string, string][] = [
  ["Does Jobreach send emails for me?",
    "Only if you ask it to. By default each letter waits in your Gmail drafts with the resume attached, and you press Send. If you turn on Send for me, letters that passed every check go from your own Gmail, a few a day inside the hours you choose, and you can stop any one before it goes."],
  ["Will it put things on my resume that I haven't done?",
    "No. Every line comes from your CV, your project notes or your GitHub. Jobreach reorders and trims your own lines for each job. If a claim or a number can't be found in what you gave it, it is left out."],
  ["Where do the openings come from?",
    "From public job boards that companies run themselves and from the careers pages of companies we have checked, collected once and shared by everyone using Jobreach. You can also paste any post you find, and it stays private to you. Nothing is taken from LinkedIn."],
  ["How does it decide who to write to?",
    "Only addresses a company published for hiring: an address in the post first, then one on its careers page. A named hiring manager or founder comes before a general mailbox, when the post gives one. Addresses are never guessed."],
  ["Do I attach the resume or send a link?",
    "Either. Download the one-page PDF made for that job and attach it, or share a private link to it that you can turn off later."],
  ["Is it only for students?",
    "No. Students looking for internships, new graduates and experienced engineers switching jobs all get openings matched to their stage and years of experience."],
  ["How long does setup take?",
    "One form: your CV, your links and the roles you want. Jobreach builds your resumes from it without a long questionnaire, and you can change anything before you start."],
  ["Can I delete my data?",
    "Yes. Everything you uploaded and everything made for you can be deleted from your profile, and it is removed from your account for good."],
];

export default function Faq() {
  return (
    <section id="faq" className="px-4 py-24 sm:px-6 sm:py-32">
      <div className="mx-auto grid max-w-[1320px] gap-10 lg:grid-cols-[minmax(0,0.75fr)_minmax(0,1.25fr)] lg:gap-20">
        <div>
          <h2 className="text-balance text-[34px] font-bold leading-[1.08] tracking-[-0.03em] sm:text-[48px] lg:sticky lg:top-28">Questions people ask</h2>
        </div>
        <div className="border-b border-border">
          {QA.map(([q, a]) => (
            <details key={q} className="faq group border-t border-border">
              <summary className="flex cursor-pointer list-none items-center gap-4 py-6 text-[18px] font-semibold tracking-[-0.01em] sm:text-[20px] [&::-webkit-details-marker]:hidden">
                <span className="flex-1">{q}</span>
                <span className="grid size-9 shrink-0 place-items-center rounded-full bg-sunken text-text-2 transition-transform duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] group-open:rotate-180">
                  <IconChevronDown size={18} />
                </span>
              </summary>
              <p className="max-w-[62ch] pb-7 pr-12 text-[17px] leading-relaxed text-text-2">{a}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}
