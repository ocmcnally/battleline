import { createClient } from "@supabase/supabase-js";

const url = import.meta.env.VITE_SUPABASE_URL as string;
const key = import.meta.env.VITE_SUPABASE_ANON_KEY as string;

export const supabase = createClient(url, key);

export interface Profile {
  id:           string;
  display_name: string;
}

export async function fetchProfile(userId: string): Promise<Profile | null> {
  const { data } = await supabase
    .from("profiles")
    .select("id, display_name")
    .eq("id", userId)
    .single();
  return data ?? null;
}

export async function createProfile(userId: string, displayName: string): Promise<void> {
  await supabase
    .from("profiles")
    .insert({ id: userId, display_name: displayName });
}
