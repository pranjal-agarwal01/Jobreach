import { createClient } from "@supabase/supabase-js";

// Publishable key: safe in the browser. Row-level security protects the data.
export const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
);
