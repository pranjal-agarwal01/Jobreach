"use client";

import { useEffect, useRef } from "react";
import { IconX } from "./icons";

/** A PDF shown full screen over the page; Escape or a click outside closes it. */
export default function PdfDialog({ url, name, onClose }: { url: string; name: string; onClose: () => void }) {
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div role="dialog" aria-modal="true" aria-label={name} className="fixed inset-0 z-50 flex flex-col bg-[rgb(11_16_32/0.72)] p-3 backdrop-blur-sm sm:p-8" onClick={onClose}>
      <div className="mx-auto flex w-full max-w-4xl items-center justify-between pb-3 text-white">
        <span className="truncate text-sm font-semibold">{name}</span>
        <button ref={closeRef} onClick={onClose} className="grid size-10 place-items-center rounded-full hover:bg-white/10" aria-label="Close preview"><IconX size={20} /></button>
      </div>
      <iframe src={url} title={name} className="mx-auto w-full max-w-4xl flex-1 rounded-md bg-white" onClick={(e) => e.stopPropagation()} />
    </div>
  );
}
