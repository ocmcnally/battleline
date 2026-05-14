import { createClient, type Session } from "@supabase/supabase-js";
import type { RatingCategory, CategoryRating } from "../types";

const url = import.meta.env.VITE_SUPABASE_URL as string;
const key = import.meta.env.VITE_SUPABASE_ANON_KEY as string;

export const supabase = createClient(url, key);

const RATING_COLS =
  "bullet_rating, bullet_games_played," +
  "blitz_rating,  blitz_games_played," +
  "rapid_rating,  rapid_games_played";

const PROFILE_COLS = `id, display_name, username_customized, ${RATING_COLS}`;

const PROVISIONAL_THRESHOLD = 10;

export interface Profile {
  id:                  string;
  display_name:        string;
  username_customized: boolean;
  bullet_rating:       number | null;
  bullet_games_played: number | null;
  blitz_rating:        number | null;
  blitz_games_played:  number | null;
  rapid_rating:        number | null;
  rapid_games_played:  number | null;
}

export function profileRatings(p: Profile): Record<RatingCategory, CategoryRating | null> {
  const cat = (r: number | null, g: number | null): CategoryRating | null =>
    r == null ? null : { rating: Math.round(r), provisional: (g ?? 0) < PROVISIONAL_THRESHOLD };
  return {
    bullet: cat(p.bullet_rating, p.bullet_games_played),
    blitz:  cat(p.blitz_rating,  p.blitz_games_played),
    rapid:  cat(p.rapid_rating,  p.rapid_games_played),
  };
}

// Fetches the profile, creating it from OAuth metadata if it doesn't exist yet.
export async function getOrCreateProfile(session: Session): Promise<Profile | null> {
  const { data: existing, error: fetchErr } = await supabase
    .from("profiles")
    .select(PROFILE_COLS)
    .eq("id", session.user.id)
    .single();

  if (existing) return existing;

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
    .select(PROFILE_COLS)
    .single();

  if (insertErr) {
    console.error("[profile] insert error:", insertErr);
    const { data: retry } = await supabase
      .from("profiles")
      .select(PROFILE_COLS)
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
