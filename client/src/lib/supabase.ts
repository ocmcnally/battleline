import { createClient, type Session } from "@supabase/supabase-js";

const url = import.meta.env.VITE_SUPABASE_URL as string;
const key = import.meta.env.VITE_SUPABASE_ANON_KEY as string;

export const supabase = createClient(url, key);

export interface Profile {
  id:           string;
  display_name: string;
}

// Fetches the profile, creating it from OAuth metadata if it doesn't exist yet.
// Handles the case where the DB trigger hasn't been set up.
export async function getOrCreateProfile(session: Session): Promise<Profile | null> {
  const { data: existing } = await supabase
    .from("profiles")
    .select("id, display_name")
    .eq("id", session.user.id)
    .single();

  if (existing) return existing;

  const displayName =
    (session.user.user_metadata?.full_name as string | undefined) ??
    (session.user.user_metadata?.name    as string | undefined) ??
    session.user.email?.split("@")[0] ??
    "Player";

  const { data: created } = await supabase
    .from("profiles")
    .insert({ id: session.user.id, display_name: displayName })
    .select("id, display_name")
    .single();

  return created ?? null;
}
