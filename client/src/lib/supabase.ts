import { createClient, type Session } from "@supabase/supabase-js";

const url = import.meta.env.VITE_SUPABASE_URL as string;
const key = import.meta.env.VITE_SUPABASE_ANON_KEY as string;

export const supabase = createClient(url, key);

export interface Profile {
  id:           string;
  display_name: string;
}

// Fetches the profile, creating it from OAuth metadata if it doesn't exist yet.
export async function getOrCreateProfile(session: Session): Promise<Profile | null> {
  const { data: existing, error: fetchErr } = await supabase
    .from("profiles")
    .select("id, display_name")
    .eq("id", session.user.id)
    .single();

  if (existing) return existing;

  // PGRST116 = "0 rows" — expected on first login, not a real error
  if (fetchErr && fetchErr.code !== "PGRST116") {
    console.error("[profile] fetch error:", fetchErr);
    return null;
  }

  const displayName =
    (session.user.user_metadata?.full_name as string | undefined) ??
    (session.user.user_metadata?.name    as string | undefined) ??
    session.user.email?.split("@")[0] ??
    "Player";

  const { data: created, error: insertErr } = await supabase
    .from("profiles")
    .insert({ id: session.user.id, display_name: displayName })
    .select("id, display_name")
    .single();

  if (insertErr) {
    console.error("[profile] insert error:", insertErr);
    // Row may have been created by a DB trigger between our fetch and insert — retry
    const { data: retry } = await supabase
      .from("profiles")
      .select("id, display_name")
      .eq("id", session.user.id)
      .single();
    return retry ?? null;
  }

  return created;
}
