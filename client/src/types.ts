// ── Card types ────────────────────────────────────────────────────────────────

export type TroopCard   = { type: "troop";   suit: string; value: number };
export type TacticsCard = { type: "tactics"; name: string };
export type WildCard    = { type: "wild";    tactic_name: string; suit: string | null; value: number | null };
export type CardData    = TroopCard | TacticsCard | WildCard;

// ── Game state ────────────────────────────────────────────────────────────────

export interface TotemData {
  index:        number;
  my_cards:     CardData[];
  opp_cards:    CardData[];
  claimed_by:   "me" | "opp" | null;
  fog:          boolean;
  mud:          boolean;
  cards_to_win: number;
}

export interface RatingChange {
  before:             number;
  after:              number;
  provisional_before: boolean;
  provisional_after:  boolean;
}

export interface GameState {
  my_hand:           CardData[];
  totems:            TotemData[];
  my_totem_count:    number;
  opp_totem_count:   number;
  troop_deck_size:   number;
  tactics_deck_size: number;
  discarded:         CardData[];
  my_turn:           boolean;
  winner:            "me" | "opp" | null;
  my_tactics_played:   number;
  opp_tactics_played:  number;
  opp_tactics_in_hand: number;
  leaders_in_play:   string[];
  names:             { me: string; opp: string };
  clock:             ClockState | null;
  rated:             boolean;
  category:          RatingCategory | null;
  rating_change:     { me: RatingChange | null; opp: RatingChange | null } | null;
}

// ── WebSocket messages ────────────────────────────────────────────────────────

export type WsMessage =
  | { type: "waiting";    game_id?: string | null }
  | { type: "game_start"; game_id: string; player_idx: number; state: GameState }
  | { type: "state";      game_id: string; state: GameState }
  | { type: "error";      message: string }
  | { type: "pong" };

// ── Auth (dummy for now) ──────────────────────────────────────────────────────

export type RatingCategory = "bullet" | "blitz" | "rapid";

export interface CategoryRating {
  rating:      number;
  provisional: boolean;
}

export interface User {
  displayName: string;
  token:       string;
  ratings:     Record<RatingCategory, CategoryRating | null>;
}

// ── Lobby ─────────────────────────────────────────────────────────────────────

export interface ClockState {
  my_remaining_ms:    number;
  opp_remaining_ms:   number;
  last_turn_start_ms: number;
  increment_ms:       number;
}

export interface OpenGame {
  game_id:             string;
  creator:             string;
  created_at:          number;
  time_label:          string;
  rated:               boolean;
  creator_rating:      number | null;
  creator_provisional: boolean | null;
}
