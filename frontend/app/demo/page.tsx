"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { setDemo } from "@/lib/demo";

/** Development only: fills every screen with a made-up student. Exit from the banner.
 *  /demo?to=/jobs opens a given screen. */
export default function Demo() {
  const router = useRouter();
  useEffect(() => {
    if (process.env.NODE_ENV === "production") { router.replace("/login"); return; }
    setDemo(true);
    const to = new URLSearchParams(window.location.search).get("to") ?? "";
    router.replace(/^\/[a-z0-9/_\-?=&]*$/i.test(to) && !to.startsWith("//") ? to : "/today");
  }, [router]);
  return null;
}
