import { createClient, type Session } from "@supabase/supabase-js";

const url = import.meta.env.VITE_SUPABASE_URL as string;
const key = import.meta.env.VITE_SUPABASE_ANON_KEY as string;

export const supabase = createClient(url, key);

export interface Profile {
  id:                  string;
  display_name:        string;
  username_customized: boolean;
  rating:              number;
  rd:                  number;
  games_played:        number;
}

// Fetches the profile, creating it from OAuth metadata if it doesn't exist yet.
export async function getOrCreateProfile(session: Session): Promise<Profile | null> {
  const { data: existing, error: fetchErr } = await supabase
    .from("profiles")
    .select("id, display_name, username_customized, rating, rd, games_played")
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
    .insert({ id: session.user.id, display_name: displayName, username_customized: false })
    .select("id, display_name, username_customized, rating, rd, games_played")
    .single();

  if (insertErr) {
    console.error("[profile] insert error:", insertErr);
    const { data: retry } = await supabase
      .from("profiles")
      .select("id, display_name, username_customized, rating, rd, games_played")
      .eq("id", session.user.id)
      .single();
    return retry ?? null;
  }

  return created;
}

export async function updateUsername(userId: string, displayName: string): Promise<string | null> {
  const { error } = await supabase
    .from("profiles")
    .update({ display_name: displayName, username_customized: true })
    .eq("id", userId);
  return error ? error.message : null;
}
