// ── Card types ────────────────────────────────────────────────────────────────

export type TroopCard   = { type: "troop";   suit: string; value: number };
export type TacticsCard = { type: "tactics"; name: string };
export type WildCard    = { type: "wild";    tactic_name: string; suit: string; value: number };
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
  my_tactics_played:  number;
  opp_tactics_played: number;
  leaders_in_play:   string[];
  names:             { me: string; opp: string };
}

// ── WebSocket messages ────────────────────────────────────────────────────────

export type WsMessage =
  | { type: "waiting";    game_id?: string | null }
  | { type: "game_start"; game_id: string; player_idx: number; state: GameState }
  | { type: "state";      game_id: string; state: GameState }
  | { type: "error";      message: string }
  | { type: "pong" };

// ── Auth (dummy for now) ──────────────────────────────────────────────────────

export interface User {
  displayName: string;
  token: string;   // client-generated UUID, used as player identifier
}

// ── Lobby ─────────────────────────────────────────────────────────────────────

export interface OpenGame {
  game_id:    string;
  creator:    string;
  created_at: number;
}
