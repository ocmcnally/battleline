"""
Battle Line — GUI (tkinter) with full Tactics deck support.
"""
import tkinter as tk
from tkinter import messagebox
import sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from battleline import (
    BattleLineGame, Card, WildCard, TacticsCard,
    SUITS, SUIT_ABBR, TACTICS_DESC,
    NUM_TOTEMS, WIN_TOTEMS, WIN_STREAK,
    ai_make_move,
)
from training.battleline_features import (
    BattleLineNet,
    legal_troop_moves,
    to_tensor,
    encode,
    legal_mask,
)
from training.utils import avg_formation_quality, claim_formation_bonus
from training.game_saver import save_game

try:
    import torch
except ImportError:
    torch = None

# ─── Palette ──────────────────────────────────────────────────────────────────
SUIT_CLR = {
    "blue": "#4d88ff", "red": "#ff3333", "orange": "#ff8c00",
    "yellow": "#ccaa00", "green": "#33aa33", "purple": "#9933ff",
}
BG      = "#1a5c2a"
DARK    = "#0d3d1a"
DARKER  = "#0a2e13"
EMPTY_F = "#1f6b30"
EMPTY_O = "#2d8a40"
GOLD    = "#ffd700"
OPP_RED = "#cc3333"
NEUTRAL = "#555555"
WHITE   = "#ffffff"
DIM_CLR = "#88aa88"
TAC_BG  = "#2a1a4a"   # tactics card background (dark purple)
TAC_OUT = "#9944ff"   # tactics card outline

# ─── Card & layout ────────────────────────────────────────────────────────────
CW, CH, CR = 70, 46, 5
GAP   = 14
COL_W = CW + GAP

CANVAS_W = NUM_TOTEMS * COL_W + 40
CANVAS_H = 390

LBL_Y = 22
OPP_Y = [50, 102, 154]    # opponent slots (0 = nearest to totem)
TOT_Y = 196
MY_Y  = [240, 292, 344]   # player slots


def col_cx(i: int) -> int:
    return 20 + i * COL_W + COL_W // 2


def rrect(cv, x1, y1, x2, y2, r=CR, **kw):
    pts = [
        x1+r, y1,  x2-r, y1,  x2, y1,
        x2, y1+r,  x2, y2-r,  x2, y2,
        x2-r, y2,  x1+r, y2,  x1, y2,
        x1, y2-r,  x1, y1+r,  x1, y1,
    ]
    cv.create_polygon(pts, smooth=True, **kw)


# ─── Main GUI ─────────────────────────────────────────────────────────────────

class BattleLineGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Battle Line")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)

        self.game:     BattleLineGame | None = None
        self.sel:      int | None  = None    # selected hand-card index
        self.pov:      int         = 0
        self.is_ai:    list[bool]  = [False, True]
        self.msg:      str         = ""
        self.nn_model: object | None = None  # trained NN model
        self.move_history: list = []  # track moves for saving
        # action-mode state machine
        # None  = normal play
        # {"type": "env",  "tactic": t}
        # {"type": "wild", "tactic": t, "suit": s, "value": v}
        # {"type": "redeploy_src", "tactic": t}
        # {"type": "redeploy_dst", "tactic": t, "from_t": i, "card": c}
        # {"type": "traitor_src",  "tactic": t}
        # {"type": "traitor_dst",  "tactic": t, "from_t": i, "card": c}
        # {"type": "deserter",     "tactic": t}
        self._astate:  dict | None = None
        self._awaiting_draw: bool  = False

        self._start_screen()

    # ── helpers ───────────────────────────────────────────────────────────────

    def _scx(self, w): return max(0, (self.root.winfo_screenwidth()  - w) // 2)
    def _scy(self, h): return max(0, (self.root.winfo_screenheight() - h) // 2)
    def _resize(self, w, h): self.root.geometry(f"{w}x{h}+{self._scx(w)}+{self._scy(h)}")
    def _clear(self):
        for w in self.root.winfo_children(): w.destroy()

    # ══ Start screen ══════════════════════════════════════════════════════════

    def _start_screen(self):
        self._clear()
        self._resize(580, 500)
        f = tk.Frame(self.root, bg=BG, padx=60, pady=36)
        f.pack(expand=True, fill=tk.BOTH)

        tk.Label(f, text="BATTLE LINE", font=("Helvetica", 38, "bold"),
                 fg=GOLD, bg=BG).pack(pady=(0, 4))
        tk.Label(f, text="A game of tactics and nerve",
                 font=("Helvetica", 12), fg=DIM_CLR, bg=BG).pack()
        tk.Frame(f, bg="#3d8b4a", height=1).pack(fill=tk.X, pady=22)

        gf = tk.Frame(f, bg=BG)
        gf.pack()

        def lbl(r, text):
            tk.Label(gf, text=text, font=("Helvetica", 12), fg=WHITE,
                     bg=BG, anchor="e").grid(row=r, column=0, sticky="e",
                                              pady=6, padx=(0, 10))
        lbl(0, "Your name:")
        self._name_var = tk.StringVar(value="Player 1")
        tk.Entry(gf, textvariable=self._name_var, font=("Helvetica", 12),
                 width=18, bg="#2a6b35", fg=WHITE, insertbackground=WHITE,
                 relief=tk.FLAT, bd=3).grid(row=0, column=1, sticky="w")

        lbl(1, "Opponent:")
        self._mode_var = tk.IntVar(value=2)
        mf = tk.Frame(gf, bg=BG)
        mf.grid(row=1, column=1, sticky="w")
        for txt, val in [("AI", 2), ("Human (pass & play)", 1)]:
            tk.Radiobutton(mf, text=txt, variable=self._mode_var, value=val,
                           font=("Helvetica", 12), fg=WHITE, bg=BG,
                           selectcolor=DARK, activebackground=BG,
                           activeforeground=WHITE).pack(side=tk.LEFT, padx=(0, 12))

        tk.Frame(f, bg="#3d8b4a", height=1).pack(fill=tk.X, pady=22)
        tk.Button(f, text="   Start Game   ", font=("Helvetica", 14, "bold"),
                  bg=GOLD, fg=DARK, relief=tk.FLAT, cursor="hand2",
                  command=self._start_game, padx=6, pady=5).pack()
        tk.Label(f,
                 text="Win 5 totems  OR  3 consecutive  ·  Tactics deck: 10 special cards",
                 font=("Helvetica", 10), fg="#668866", bg=BG).pack(pady=14)

    def _start_game(self):
        mode = self._mode_var.get()
        p0   = self._name_var.get().strip() or "Player 1"
        p1   = "AI" if mode == 2 else "Player 2"
        self.game        = BattleLineGame([p0, p1])
        # Capture initial state immediately after creation so we can save it
        # later for accurate replay. After __init__ the deck is already dealt,
        # so we snapshot hands and remaining deck right here.
        self._initial_hands  = [list(self.game.hands[0]), list(self.game.hands[1])]
        self._initial_deck   = list(self.game.deck)
        self.training_moves  = []   # (features, mask, action_idx, player, step_bonus)
        self._pre_move_state = None  # set in _capture_training_move, consumed in _finalize_training_move
        self.is_ai       = [False, mode == 2]
        self.pov         = 0
        self.sel         = None
        self._astate     = None
        self._awaiting_draw = False
        self.msg         = f"{p0}'s turn — select a card, then click a totem."
        
        # Load trained NN model if AI is enabled
        if mode == 2 and torch is not None:
            try:
                self.nn_model = BattleLineNet()
                self.nn_model.load_state_dict(torch.load("training/battleline_model.pt", weights_only=True))
                self.nn_model.eval()
                self.msg = f"{p0}'s turn — select a card. Playing against Neural Network AI."
            except Exception as e:
                self.msg = f"Failed to load NN model: {e}. Using greedy AI instead."
                self.nn_model = None
        
        self._game_screen()
        self._refresh()

    # ══ Game screen ═══════════════════════════════════════════════════════════

    def _game_screen(self):
        self._clear()
        win_w = CANVAS_W + 40
        win_h = CANVAS_H + 230
        self._resize(win_w, win_h)

        # top bar
        top = tk.Frame(self.root, bg=DARK, pady=7)
        top.pack(fill=tk.X)
        tk.Label(top, text="BATTLE LINE", font=("Helvetica", 13, "bold"),
                 fg=GOLD, bg=DARK).pack(side=tk.LEFT, padx=14)
        self._score_lbl = tk.Label(top, text="", font=("Helvetica", 11),
                                    fg=WHITE, bg=DARK)
        self._score_lbl.pack(side=tk.LEFT, padx=8)
        self._deck_lbl = tk.Label(top, text="", font=("Helvetica", 10),
                                   fg=DIM_CLR, bg=DARK)
        self._deck_lbl.pack(side=tk.RIGHT, padx=14)
        tk.Button(top, text="Menu", font=("Helvetica", 10), bg=DARK, fg=DIM_CLR,
                  relief=tk.FLAT, cursor="hand2", bd=0,
                  command=self._start_screen).pack(side=tk.RIGHT, padx=8)

        # board canvas
        self._cv = tk.Canvas(self.root, width=CANVAS_W, height=CANVAS_H,
                              bg=BG, highlightthickness=0)
        self._cv.pack(padx=20, pady=(8, 2))
        self._cv.bind("<Button-1>", self._board_click)

        # opponent info
        opp_bar = tk.Frame(self.root, bg=DARK, pady=3)
        opp_bar.pack(fill=tk.X, padx=20)
        self._opp_lbl = tk.Label(opp_bar, text="", font=("Helvetica", 10),
                                  fg=DIM_CLR, bg=DARK)
        self._opp_lbl.pack(side=tk.LEFT, padx=10)

        # player hand row
        hand_bar = tk.Frame(self.root, bg=DARK, pady=6)
        hand_bar.pack(fill=tk.X, padx=20)
        tk.Label(hand_bar, text="YOUR HAND ▶", font=("Helvetica", 9, "bold"),
                 fg=DIM_CLR, bg=DARK).pack(side=tk.LEFT, padx=(10, 14))
        self._hand_f = tk.Frame(hand_bar, bg=DARK)
        self._hand_f.pack(side=tk.LEFT)

        # draw buttons row (hidden until needed)
        self._draw_bar = tk.Frame(self.root, bg=DARKER, pady=5)
        self._draw_bar.pack(fill=tk.X, padx=20)
        self._draw_bar_inner = tk.Frame(self._draw_bar, bg=DARKER)
        self._draw_bar_inner.pack()

        # status bar
        stat = tk.Frame(self.root, bg=DARKER, pady=6)
        stat.pack(fill=tk.X)
        self._msg_lbl = tk.Label(stat, text="", font=("Helvetica", 11),
                                  fg=WHITE, bg=DARKER, anchor="w",
                                  wraplength=CANVAS_W + 10)
        self._msg_lbl.pack(fill=tk.X, padx=14)

    # ══ Drawing ═══════════════════════════════════════════════════════════════

    def _draw_card(self, cv, x, y, card, sel=False):
        x1, y1 = x - CW // 2, y - CH // 2
        x2, y2 = x + CW // 2, y + CH // 2

        if card is None:
            rrect(cv, x1, y1, x2, y2, fill=EMPTY_F, outline=EMPTY_O, width=1)
            return

        if isinstance(card, TacticsCard):
            # shouldn't appear on board, but handle gracefully
            rrect(cv, x1, y1, x2, y2, fill=TAC_BG, outline=TAC_OUT, width=2)
            cv.create_text(x, y, text=card.name[:4].upper(),
                           font=("Helvetica", 9, "bold"), fill=WHITE)
            return

        fill = SUIT_CLR[card.suit]
        outl = GOLD if sel else "#dddddd"
        bw   = 3    if sel else 1
        if isinstance(card, WildCard):
            outl = "#dd88ff" if not sel else GOLD
            bw   = 2
        rrect(cv, x1, y1, x2, y2, fill=fill, outline=outl, width=bw)
        cv.create_text(x1 + 7, y1 + 8, text=SUIT_ABBR[card.suit],
                       font=("Helvetica", 8, "bold"), fill=WHITE, anchor="nw")
        cv.create_text(x, y, text=str(card.value),
                       font=("Helvetica", 16, "bold"), fill=WHITE)
        if isinstance(card, WildCard):
            cv.create_text(x2 - 6, y2 - 7, text="★",
                           font=("Helvetica", 7), fill="#dd88ff", anchor="se")

    def _draw_tac_hand_card(self, parent, tac: TacticsCard, idx: int, sel: bool):
        """Draw a tactics card in the hand area."""
        hc = tk.Canvas(parent, width=CW + 6, height=CH + 12,
                        bg=DARK, highlightthickness=0, cursor="hand2")
        hc.pack(side=tk.LEFT, padx=3)
        if sel:
            hc.create_rectangle(1, CH + 4, CW + 5, CH + 12, fill=GOLD, outline="")
        x, y = (CW + 6) // 2, (CH + 12) // 2 - 1
        x1, y1 = x - CW // 2, y - CH // 2
        x2, y2 = x + CW // 2, y + CH // 2
        rrect(hc, x1, y1, x2, y2,
              fill=TAC_BG, outline=GOLD if sel else TAC_OUT, width=2 if sel else 1)
        short = {"alexander": "ALEX", "darius": "DARI", "wild8": "W-8",
                 "wild321": "W-321", "fog": "FOG", "mud": "MUD",
                 "scout": "SCOUT", "redeploy": "REPL", "traitor": "TRAI",
                 "deserter": "DESE"}
        hc.create_text(x, y - 4, text=short.get(tac.name, tac.name[:4].upper()),
                       font=("Helvetica", 9, "bold"), fill=WHITE)
        hc.create_text(x, y + 10, text="TACTICS",
                       font=("Helvetica", 6), fill=TAC_OUT)
        if sel:
            hc.create_rectangle(1, CH + 4, CW + 5, CH + 12, fill=GOLD, outline="")
        hc.bind("<Button-1>", lambda e, i=idx: self._hand_click(i))
        return hc

    # ══ Refresh ═══════════════════════════════════════════════════════════════

    def _refresh(self):
        g = self.game
        if g is None:
            return

        # labels
        p0c = sum(1 for t in g.totems if t.claimed == 0)
        p1c = sum(1 for t in g.totems if t.claimed == 1)
        self._score_lbl.config(
            text=f"{g.names[0]}: {p0c}  ·  {g.names[1]}: {p1c}"
                 f"  (need {WIN_TOTEMS} or {WIN_STREAK} consecutive)")
        tc0, tc1 = g.tactics_played
        self._deck_lbl.config(
            text=f"Troop: {len(g.deck)}  Tactics: {len(g.tactics_deck)}"
                 f"  |  Tac played: {g.names[0]}={tc0} {g.names[1]}={tc1}")
        opp = 1 - self.pov
        self._opp_lbl.config(
            text=f"{g.names[opp]}: {len(g.hands[opp])} cards in hand")
        self._msg_lbl.config(text=self.msg)

        # draw buttons
        for w in self._draw_bar_inner.winfo_children():
            w.destroy()
        if self._awaiting_draw:
            tk.Label(self._draw_bar_inner, text="Draw from:",
                     font=("Helvetica", 11), fg=WHITE, bg=DARKER).pack(side=tk.LEFT, padx=8)
            if g.deck:
                tk.Button(self._draw_bar_inner,
                          text=f"Troop deck ({len(g.deck)})",
                          font=("Helvetica", 11, "bold"),
                          bg=GOLD, fg=DARK, relief=tk.FLAT, cursor="hand2", padx=8, pady=3,
                          command=lambda: self._do_draw(False)).pack(side=tk.LEFT, padx=4)
            if g.tactics_deck:
                tk.Button(self._draw_bar_inner,
                          text=f"Tactics deck ({len(g.tactics_deck)})",
                          font=("Helvetica", 11, "bold"),
                          bg=TAC_OUT, fg=WHITE, relief=tk.FLAT, cursor="hand2", padx=8, pady=3,
                          command=lambda: self._do_draw(True)).pack(side=tk.LEFT, padx=4)

        # board
        cv = self._cv
        cv.delete("all")

        astate = self._astate

        for i, totem in enumerate(g.totems):
            x = col_cx(i)

            # column label
            cv.create_text(x, LBL_Y, text=str(i + 1),
                           font=("Helvetica", 10, "bold"), fill="#77aa77")

            # fog / mud labels
            env_txt = ""
            if totem.fog: env_txt += "FOG "
            if totem.mud: env_txt += "MUD"
            if env_txt:
                cv.create_text(x, LBL_Y + 14, text=env_txt.strip(),
                               font=("Helvetica", 7, "bold"), fill="#aaaaff")

            # totem indicator
            if totem.claimed == self.pov:
                tc, tt, tf = GOLD,    "YOU", "black"
            elif totem.claimed is not None:
                tc, tt, tf = OPP_RED, "OPP", WHITE
            else:
                tc, tt, tf = NEUTRAL, "·",   "#aaaaaa"

            cv.create_oval(x - 17, TOT_Y - 13, x + 17, TOT_Y + 13,
                           fill=tc, outline="")
            cv.create_text(x, TOT_Y, text=tt,
                           font=("Helvetica", 7, "bold"), fill=tf)

            for dy in (-16, 16):
                cv.create_line(x - CW // 2, TOT_Y + dy,
                               x + CW // 2, TOT_Y + dy,
                               fill="#2a7a35", width=1)

            # Mud: show 4th slot for both sides
            ctw = totem.cards_to_win
            opp_y_slots = OPP_Y if ctw == 3 else [OPP_Y[0] - 52] + list(OPP_Y)
            my_y_slots  = MY_Y  if ctw == 3 else list(MY_Y) + [MY_Y[2] + 52]

            # opponent cards
            for slot in range(ctw):
                ypos = opp_y_slots[slot] if slot < len(opp_y_slots) else OPP_Y[-1] - 52 * (slot - 2)
                c = totem.sides[opp][slot] if slot < len(totem.sides[opp]) else None
                # highlight for traitor/deserter source selection
                is_tgt = (astate and astate["type"] in ("traitor_src", "deserter")
                          and c is not None and totem.claimed is None)
                self._draw_card(cv, x, ypos, c, sel=is_tgt)

            # player cards
            for slot in range(ctw):
                ypos = my_y_slots[slot] if slot < len(my_y_slots) else MY_Y[-1] + 52 * (slot - 2)
                c = totem.sides[self.pov][slot] if slot < len(totem.sides[self.pov]) else None
                # highlight for redeploy source selection
                is_src = (astate and astate["type"] == "redeploy_src"
                          and c is not None and totem.claimed is None)
                self._draw_card(cv, x, ypos, c, sel=is_src)

            # dashed highlight: normal play mode
            is_my_turn  = g.turn % 2 == self.pov and not self._awaiting_draw
            is_playable = totem.claimed is None and not totem.is_full(self.pov)

            if not astate and self.sel is not None and is_my_turn and is_playable:
                cv.create_rectangle(
                    x - COL_W // 2 + 3, MY_Y[0] - CH // 2 - 4,
                    x + COL_W // 2 - 3, MY_Y[2] + CH // 2 + 4,
                    outline=GOLD, fill="", width=2, dash=(6, 3))

            # dashed highlight: env/wild placement mode
            if astate and astate["type"] in ("env", "wild") and is_my_turn:
                if totem.claimed is None and (
                        astate["type"] == "env" or is_playable):
                    cv.create_rectangle(
                        x - COL_W // 2 + 3, 30,
                        x + COL_W // 2 - 3, CANVAS_H - 10,
                        outline=TAC_OUT, fill="", width=2, dash=(4, 3))

            # highlight destination columns for redeploy_dst / traitor_dst
            if (astate and astate["type"] in ("redeploy_dst", "traitor_dst")
                    and is_playable):
                cv.create_rectangle(
                    x - COL_W // 2 + 3, MY_Y[0] - CH // 2 - 4,
                    x + COL_W // 2 - 3, MY_Y[2] + CH // 2 + 4,
                    outline="#44ffaa", fill="", width=2, dash=(6, 3))

        # hand
        for w in self._hand_f.winfo_children():
            w.destroy()

        for idx, card in enumerate(g.hands[self.pov]):
            sel = (idx == self.sel)
            if isinstance(card, TacticsCard):
                self._draw_tac_hand_card(self._hand_f, card, idx, sel)
            else:
                hc = tk.Canvas(self._hand_f, width=CW + 6, height=CH + 12,
                                bg=DARK, highlightthickness=0, cursor="hand2")
                hc.pack(side=tk.LEFT, padx=3)
                if sel:
                    hc.create_rectangle(1, CH + 4, CW + 5, CH + 12,
                                        fill=GOLD, outline="")
                self._draw_card(hc, (CW + 6) // 2, (CH + 12) // 2 - 1, card, sel=sel)
                hc.bind("<Button-1>", lambda e, i=idx: self._hand_click(i))

        if g.winner is not None:
            self.root.after(300, self._show_winner)

    # ══ Interactions ══════════════════════════════════════════════════════════

    def _hand_click(self, idx: int):
        g = self.game
        if not g or g.winner is not None or self._awaiting_draw:
            return
        if g.turn % 2 != self.pov:
            return

        card = g.hands[self.pov][idx]

        if isinstance(card, TacticsCard):
            self._handle_tactics_click(idx, card)
        else:
            # regular card selection
            self._astate = None
            if self.sel == idx:
                self.sel = None
                self.msg = "Card deselected."
            else:
                self.sel = idx
                self.msg = (f"Selected {card.suit.capitalize()} {card.value} — "
                            f"click a highlighted totem to play it.")
            self._refresh()

    def _handle_tactics_click(self, idx: int, tac: TacticsCard):
        g = self.game
        if not g.can_play_tactics(self.pov):
            self.msg = "Can't play tactics — you're already 1 ahead of your opponent."
            self._refresh()
            return

        self.sel = idx  # keep selected so user knows which card

        if tac.is_wild:
            self._dialog_wild_assign(tac)
        elif tac.is_environment:
            self._astate = {"type": "env", "tactic": tac}
            self.msg = f"[{tac.name.upper()}] Click a totem to apply {tac.name}."
            self._refresh()
        elif tac.name == "scout":
            self._dialog_scout(tac)
        elif tac.name == "redeploy":
            self._astate = {"type": "redeploy_src", "tactic": tac}
            self.msg = "[REDEPLOY] Click one of your cards on the board to move or discard it."
            self._refresh()
        elif tac.name == "traitor":
            self._astate = {"type": "traitor_src", "tactic": tac}
            self.msg = "[TRAITOR] Click one of your opponent's cards on the board to steal."
            self._refresh()
        elif tac.name == "deserter":
            self._astate = {"type": "deserter", "tactic": tac}
            self.msg = "[DESERTER] Click one of your opponent's cards on the board to discard."
            self._refresh()

    def _board_click(self, ev):
        g = self.game
        if not g or g.winner is not None or self._awaiting_draw:
            return
        if g.turn % 2 != self.pov:
            self.msg = "It's not your turn!"
            self._refresh()
            return

        x, y = ev.x, ev.y
        zone, ti, slot = self._hit_test(x, y)
        astate = self._astate

        # ── action mode handlers ──────────────────────────────────────────────

        if astate:
            atype = astate["type"]

            if atype == "env":
                if zone == "col" and ti is not None:
                    try:
                        msg = g.play_environment(self.pov, astate["tactic"], ti)
                        self._finish_play(msg, needs_draw=True)
                    except ValueError as e:
                        self.msg = f"⚠  {e}"
                        self._refresh()
                return

            if atype == "wild":
                if zone in ("col", "me") and ti is not None:
                    totem = g.totems[ti]
                    if totem.claimed is not None or totem.is_full(self.pov):
                        self.msg = f"⚠  Can't play there."
                        self._refresh()
                        return
                    try:
                        msg = g.play_wild(self.pov, astate["tactic"], ti,
                                          astate["suit"], astate["value"])
                        self._finish_play(msg, needs_draw=True)
                    except ValueError as e:
                        self.msg = f"⚠  {e}"
                        self._refresh()
                return

            if atype == "redeploy_src":
                if zone == "me" and ti is not None and slot is not None:
                    totem = g.totems[ti]
                    if totem.claimed is None and slot < len(totem.sides[self.pov]):
                        card = totem.sides[self.pov][slot]
                        self._astate = {"type": "redeploy_dst",
                                        "tactic": astate["tactic"],
                                        "from_t": ti, "card": card}
                        self.msg = (f"[REDEPLOY] Selected card from totem {ti+1}. "
                                    f"Now click a destination totem — "
                                    f"or press Discard below.")
                        self._show_discard_button(lambda: self._redeploy_discard())
                        self._refresh()
                return

            if atype == "redeploy_dst":
                if zone in ("col", "me") and ti is not None:
                    try:
                        msg = g.play_redeploy(self.pov, astate["tactic"],
                                              astate["from_t"], astate["card"], ti)
                        self._hide_discard_button()
                        self._finish_play(msg, needs_draw=True)
                    except ValueError as e:
                        self.msg = f"⚠  {e}"
                        self._refresh()
                return

            if atype == "traitor_src":
                opp = 1 - self.pov
                if zone == "opp" and ti is not None and slot is not None:
                    totem = g.totems[ti]
                    if totem.claimed is None and slot < len(totem.sides[opp]):
                        card = totem.sides[opp][slot]
                        self._astate = {"type": "traitor_dst",
                                        "tactic": astate["tactic"],
                                        "from_t": ti, "card": card}
                        self.msg = (f"[TRAITOR] Targeting card from totem {ti+1}. "
                                    f"Now click your destination totem.")
                        self._refresh()
                return

            if atype == "traitor_dst":
                if zone in ("col", "me") and ti is not None:
                    try:
                        msg = g.play_traitor(self.pov, astate["tactic"],
                                             astate["from_t"], astate["card"], ti)
                        self._finish_play(msg, needs_draw=True)
                    except ValueError as e:
                        self.msg = f"⚠  {e}"
                        self._refresh()
                return

            if atype == "deserter":
                opp = 1 - self.pov
                if zone == "opp" and ti is not None and slot is not None:
                    totem = g.totems[ti]
                    if totem.claimed is None and slot < len(totem.sides[opp]):
                        card = totem.sides[opp][slot]
                        try:
                            msg = g.play_deserter(self.pov, astate["tactic"], ti, card)
                            self._finish_play(msg, needs_draw=True)
                        except ValueError as e:
                            self.msg = f"⚠  {e}"
                            self._refresh()
                return

        # ── normal play ───────────────────────────────────────────────────────

        if self.sel is None:
            self.msg = "Select a card from your hand first!"
            self._refresh()
            return

        card = g.hands[self.pov][self.sel]
        if isinstance(card, TacticsCard):
            self.msg = "Use the hand area to play tactics cards."
            self._refresh()
            return

        if zone in ("col", "me") and ti is not None:
            try:
                self._capture_training_move(self.pov, card, ti)
                msg = g.play_card(self.pov, card, ti)
                self.move_history.append([self.pov, card, ti, False])
                self.sel = None
                self._finish_play(msg, needs_draw=True)
            except ValueError as e:
                self.msg = f"⚠  {e}"
                self._refresh()

    def _hit_test(self, x, y):
        """Returns (zone, totem_idx, slot_idx).
        zone: "opp", "me", "totem", "col", None
        """
        for i in range(NUM_TOTEMS):
            cx = col_cx(i)
            if not (cx - COL_W // 2 <= x <= cx + COL_W // 2):
                continue
            for slot, oy in enumerate(OPP_Y):
                if oy - CH // 2 - 4 <= y <= oy + CH // 2 + 4:
                    return ("opp", i, slot)
            for slot, my in enumerate(MY_Y):
                if my - CH // 2 - 4 <= y <= my + CH // 2 + 4:
                    return ("me", i, slot)
            if TOT_Y - 16 <= y <= TOT_Y + 16:
                return ("totem", i, None)
            return ("col", i, None)
        return (None, None, None)

    # ── Discard button (for Redeploy) ─────────────────────────────────────────

    def _show_discard_button(self, cmd):
        for w in self._draw_bar_inner.winfo_children():
            w.destroy()
        tk.Button(self._draw_bar_inner, text="Discard card (don't move it)",
                  font=("Helvetica", 11, "bold"),
                  bg="#883333", fg=WHITE, relief=tk.FLAT, cursor="hand2",
                  padx=8, pady=3, command=cmd).pack(side=tk.LEFT, padx=4)
        tk.Button(self._draw_bar_inner, text="Cancel",
                  font=("Helvetica", 10),
                  bg=DARK, fg=DIM_CLR, relief=tk.FLAT, cursor="hand2",
                  padx=6, pady=3, command=self._cancel_action).pack(side=tk.LEFT, padx=4)

    def _hide_discard_button(self):
        for w in self._draw_bar_inner.winfo_children():
            w.destroy()

    def _redeploy_discard(self):
        g = self.game
        astate = self._astate
        if not astate or astate["type"] != "redeploy_dst":
            return
        try:
            msg = g.play_redeploy(self.pov, astate["tactic"],
                                  astate["from_t"], astate["card"], None)
            self._hide_discard_button()
            self._finish_play(msg, needs_draw=True)
        except ValueError as e:
            self.msg = f"⚠  {e}"
            self._refresh()

    def _cancel_action(self):
        self._astate = None
        self.sel = None
        self._hide_discard_button()
        self.msg = "Action cancelled."
        self._refresh()

    # ── Training data capture ─────────────────────────────────────────────────

    def _capture_training_move(self, player: int, card, ti: int) -> None:
        """Call immediately BEFORE play_card. Records pre-move state."""
        try:
            feats    = encode(self.game, player)
            msk      = legal_mask(self.game, player)
            act_idx  = None
            for c, t, idx in legal_troop_moves(self.game, player):
                if c.suit == card.suit and c.value == card.value and t == ti:
                    act_idx = idx
                    break
            if act_idx is None:
                self._pre_move_state = None
                return
            claimed_before = {i for i, t in enumerate(self.game.totems) if t.claimed == player}
            self._pre_move_state = (feats, msk, act_idx, player, claimed_before)
        except Exception:
            self._pre_move_state = None

    def _finalize_training_move(self) -> None:
        """Call immediately AFTER draw_card. Computes step_bonus and stores the example."""
        if self._pre_move_state is None:
            return
        feats, msk, act_idx, player, claimed_before = self._pre_move_state
        self._pre_move_state = None
        try:
            newly = {i for i, t in enumerate(self.game.totems)
                     if t.claimed == player and i not in claimed_before}
            step_bonus = (avg_formation_quality(self.game, player)
                          + claim_formation_bonus(self.game, player, newly))
            self.training_moves.append((feats, msk, act_idx, player, step_bonus))
        except Exception:
            pass

    # ── Play completion ───────────────────────────────────────────────────────

    def _finish_play(self, msg: str, needs_draw: bool):
        self._astate = None
        self.sel     = None
        self.msg     = msg.replace("\n", "  ·  ")
        g = self.game

        if needs_draw:
            has_troop   = bool(g.deck)
            has_tactics = bool(g.tactics_deck)
            if has_troop and has_tactics:
                self._awaiting_draw = True
                self._refresh()
                return
            elif has_troop:
                g.draw_card(self.pov, False)
            elif has_tactics:
                g.draw_card(self.pov, True)
            # else no draw

        self._complete_turn()

    def _do_draw(self, from_tactics: bool):
        self.game.draw_card(self.pov, from_tactics)
        self._awaiting_draw = False
        if self.move_history:
            self.move_history[-1][3] = from_tactics  # record which deck was drawn from
        self._complete_turn()

    def _complete_turn(self):
        g = self.game
        g.turn += 1
        self._awaiting_draw = False
        self._finalize_training_move()
        self._refresh()
        if g.winner is None:
            if self.is_ai[g.turn % 2]:
                self.root.after(700, self._ai_turn)
            elif not any(self.is_ai):
                self._pass_device()

    # ══ Tactics dialogs ═══════════════════════════════════════════════════════

    def _dialog_wild_assign(self, tac: TacticsCard):
        """Show a dialog to assign suit (and value for alexander/darius/wild321)."""
        m = tk.Toplevel(self.root)
        m.title(tac.name.capitalize())
        m.grab_set()
        m.resizable(False, False)
        m.configure(bg=DARK)
        mw = 420
        mh = 260 if tac.name in ("alexander", "darius", "wild321") else 200
        m.geometry(f"{mw}x{mh}+{self._scx(mw)}+{self._scy(mh)}")

        tk.Label(m, text=tac.name.upper(), font=("Helvetica", 16, "bold"),
                 fg=GOLD, bg=DARK).pack(pady=(16, 4))
        tk.Label(m, text=TACTICS_DESC[tac.name], font=("Helvetica", 10),
                 fg=DIM_CLR, bg=DARK).pack()
        tk.Frame(m, bg="#3d8b4a", height=1).pack(fill=tk.X, padx=20, pady=10)

        suit_var  = tk.StringVar(value=SUITS[0])
        value_var = tk.IntVar(value=8 if tac.name == "wild8" else 1)

        # suit selection
        sf = tk.Frame(m, bg=DARK)
        sf.pack()
        tk.Label(sf, text="Suit:", font=("Helvetica", 11), fg=WHITE, bg=DARK
                 ).pack(side=tk.LEFT, padx=(0, 8))
        for s in SUITS:
            tk.Radiobutton(sf, text=s[:3].capitalize(), variable=suit_var, value=s,
                           font=("Helvetica", 10), fg=SUIT_CLR[s], bg=DARK,
                           selectcolor=DARKER, activebackground=DARK,
                           activeforeground=WHITE).pack(side=tk.LEFT, padx=2)

        # value selection (for variable-value wilds)
        if tac.name in ("alexander", "darius"):
            vf = tk.Frame(m, bg=DARK)
            vf.pack(pady=6)
            tk.Label(vf, text="Value:", font=("Helvetica", 11), fg=WHITE, bg=DARK
                     ).pack(side=tk.LEFT, padx=(0, 8))
            value_var.set(10)
            tk.Scale(vf, from_=1, to=10, orient=tk.HORIZONTAL, variable=value_var,
                     bg=DARK, fg=WHITE, troughcolor=DARKER, highlightthickness=0,
                     length=200).pack(side=tk.LEFT)
        elif tac.name == "wild321":
            vf = tk.Frame(m, bg=DARK)
            vf.pack(pady=6)
            tk.Label(vf, text="Value:", font=("Helvetica", 11), fg=WHITE, bg=DARK
                     ).pack(side=tk.LEFT, padx=(0, 8))
            value_var.set(1)
            for v in (1, 2, 3):
                tk.Radiobutton(vf, text=str(v), variable=value_var, value=v,
                               font=("Helvetica", 12), fg=WHITE, bg=DARK,
                               selectcolor=DARKER, activebackground=DARK,
                               activeforeground=WHITE).pack(side=tk.LEFT, padx=6)

        def _confirm():
            s = suit_var.get()
            v = value_var.get()
            m.destroy()
            # enter wild placement mode
            self._astate = {"type": "wild", "tactic": tac, "suit": s, "value": v}
            self.msg = (f"[{tac.name.upper()}] as {s} {v} — "
                        f"click a highlighted totem to place it.")
            self._refresh()

        tk.Button(m, text="  Confirm — then click a totem  ",
                  font=("Helvetica", 12, "bold"),
                  bg=GOLD, fg=DARK, relief=tk.FLAT, cursor="hand2",
                  command=_confirm, pady=5).pack(pady=12)

    def _dialog_scout(self, tac: TacticsCard):
        """Scout dialog: choose split, see cards, return 2."""
        g = self.game
        max_troop   = min(3, len(g.deck))
        max_tactics = min(3, len(g.tactics_deck))
        if max_troop + max_tactics < 3:
            self.msg = f"⚠  Not enough cards to Scout (need 3, have {max_troop+max_tactics})."
            self.sel = None
            self._refresh()
            return

        m = tk.Toplevel(self.root)
        m.title("Scout")
        m.grab_set()
        m.resizable(False, False)
        m.configure(bg=DARK)
        mw, mh = 540, 420
        m.geometry(f"{mw}x{mh}+{self._scx(mw)}+{self._scy(mh)}")

        tk.Label(m, text="SCOUT", font=("Helvetica", 16, "bold"),
                 fg=GOLD, bg=DARK).pack(pady=(14, 2))
        tk.Label(m, text=TACTICS_DESC["scout"], font=("Helvetica", 10),
                 fg=DIM_CLR, bg=DARK).pack()
        tk.Frame(m, bg="#3d8b4a", height=1).pack(fill=tk.X, padx=20, pady=8)

        # phase 1: choose split
        phase1 = tk.Frame(m, bg=DARK)
        phase1.pack()

        tk.Label(phase1, text="How many from the Troop deck?",
                 font=("Helvetica", 11), fg=WHITE, bg=DARK).pack(pady=4)
        troop_var = tk.IntVar(value=min(3, max_troop))
        sf = tk.Frame(phase1, bg=DARK)
        sf.pack()
        for v in range(max_troop + 1):
            if 3 - v <= max_tactics:
                tk.Radiobutton(sf, text=f"{v} troop / {3-v} tactics",
                               variable=troop_var, value=v,
                               font=("Helvetica", 11), fg=WHITE, bg=DARK,
                               selectcolor=DARKER, activebackground=DARK,
                               activeforeground=WHITE).pack(anchor="w", padx=30)

        revealed_frame = tk.Frame(m, bg=DARK)
        return_vars    = []   # list of (card, dest_var) pairs

        def _do_reveal():
            phase1.pack_forget()
            tc = troop_var.get()
            tacc = 3 - tc
            try:
                revealed = g.scout_reveal(self.pov, tac, tc, tacc)
            except ValueError as e:
                m.destroy()
                self.msg = f"⚠  {e}"
                self.sel = None
                self._refresh()
                return

            revealed_frame.pack(fill=tk.BOTH, expand=True)
            tk.Label(revealed_frame,
                     text="Cards revealed — choose 2 to return to their decks:",
                     font=("Helvetica", 11), fg=WHITE, bg=DARK).pack(pady=6)

            # show all hand cards with checkboxes for return
            scroll_f = tk.Frame(revealed_frame, bg=DARK)
            scroll_f.pack(fill=tk.BOTH, expand=True, padx=20)

            nonlocal return_vars
            return_vars = []

            # show the newly revealed cards first
            tk.Label(scroll_f, text="Revealed cards (★):",
                     font=("Helvetica", 10, "bold"), fg=GOLD, bg=DARK).pack(anchor="w")
            rev_cards = {c for _, c in revealed}

            for card in g.hands[self.pov]:
                row = tk.Frame(scroll_f, bg=DARK)
                row.pack(fill=tk.X, pady=1)
                selected_var = tk.BooleanVar(value=False)
                dest_var     = tk.StringVar(value="troop" if isinstance(card, Card) and not isinstance(card, TacticsCard) else "tactics")
                star = " ★" if card in rev_cards else "  "
                if isinstance(card, TacticsCard):
                    lbl_text = f"{star}{card.name.upper()}"
                else:
                    lbl_text = f"{star}{card.suit} {card.value}"
                tk.Checkbutton(row, text=lbl_text, variable=selected_var,
                               font=("Helvetica", 11), fg=WHITE, bg=DARK,
                               selectcolor=DARKER, activebackground=DARK,
                               activeforeground=WHITE).pack(side=tk.LEFT)
                dest_f = tk.Frame(row, bg=DARK)
                dest_f.pack(side=tk.LEFT, padx=10)
                tk.Label(dest_f, text="→", fg=DIM_CLR, bg=DARK,
                         font=("Helvetica", 10)).pack(side=tk.LEFT)
                for d_txt, d_val in [("Troop deck", "troop"), ("Tactics deck", "tactics")]:
                    tk.Radiobutton(dest_f, text=d_txt, variable=dest_var, value=d_val,
                                   font=("Helvetica", 9), fg=WHITE, bg=DARK,
                                   selectcolor=DARKER, activebackground=DARK,
                                   activeforeground=WHITE).pack(side=tk.LEFT, padx=3)
                return_vars.append((card, selected_var, dest_var))

            def _do_return():
                chosen = [(c, dv.get()) for c, sv, dv in return_vars if sv.get()]
                if len(chosen) != 2:
                    messagebox.showwarning("Scout", "Select exactly 2 cards to return.",
                                           parent=m)
                    return
                try:
                    msg = g.scout_return(self.pov, chosen)
                    m.destroy()
                    # scout: no draw needed
                    self._finish_play(msg, needs_draw=False)
                except ValueError as e:
                    messagebox.showerror("Scout Error", str(e), parent=m)

            tk.Button(revealed_frame, text="  Return selected 2 cards  ",
                      font=("Helvetica", 12, "bold"),
                      bg=GOLD, fg=DARK, relief=tk.FLAT, cursor="hand2",
                      command=_do_return, pady=5).pack(pady=10)

        tk.Button(phase1, text="  Reveal cards  ",
                  font=("Helvetica", 12, "bold"),
                  bg=GOLD, fg=DARK, relief=tk.FLAT, cursor="hand2",
                  command=_do_reveal, pady=5).pack(pady=12)

    # ══ AI turn ═══════════════════════════════════════════════════════════════

    def _nn_ai_move(self, game: BattleLineGame, player: int) -> tuple[str, bool, Card | None]:
        """Get move from trained neural network model. Returns (msg, needs_draw, card_played)."""
        if not self.nn_model:
            msg, needs_draw = ai_make_move(game, player)
            return (msg, needs_draw, None)
        
        moves = legal_troop_moves(game, player)
        if not moves:
            # No legal moves, fall back to greedy AI
            msg, needs_draw = ai_make_move(game, player)
            return (msg, needs_draw, None)
        
        best_move = None
        best_logit = float('-inf')
        
        with torch.no_grad():
            policy_logits, _ = self.nn_model(to_tensor(game, player))
            logits = policy_logits.squeeze(0).cpu().numpy()
        
        # Find the highest-logit legal move
        for card, ti, action_index in moves:
            if logits[action_index] > best_logit:
                best_logit = logits[action_index]
                best_move = (card, ti, action_index)
        
        if best_move is None:
            msg, needs_draw = ai_make_move(game, player)
            return (msg, needs_draw, None)
        
        card, totem_idx, _ = best_move
        self._capture_training_move(player, card, totem_idx)
        msg = game.play_card(player, card, totem_idx)
        return (msg, True, (player, card, totem_idx))

    def _ai_turn(self):
        g = self.game
        if not g or g.winner is not None:
            return
        ai_p = g.turn % 2
        if not self.is_ai[ai_p]:
            return
        
        # Use NN model if available, otherwise use greedy AI.
        # In both cases, record the move to move_history before executing it.
        if self.nn_model:
            msg, needs_draw, move_tuple = self._nn_ai_move(g, ai_p)
            if move_tuple:
                self.move_history.append([*move_tuple, False])
        else:
            from battleline import ai_choose_move
            chosen = ai_choose_move(g, ai_p)
            if chosen is not None and chosen[0] == "card":
                _, card, ti = chosen
                self.move_history.append([ai_p, card, ti, False])
            msg, needs_draw = ai_make_move(g, ai_p)

        if needs_draw:
            g.draw_card(ai_p, False)
        self._finalize_training_move()
        self.msg = f"[{g.names[ai_p]}] {msg.replace(chr(10), '  ·  ')}"
        g.turn += 1
        self._refresh()
        if g.winner is None and self.is_ai[g.turn % 2]:
            self.root.after(700, self._ai_turn)

    # ══ Hotseat pass ══════════════════════════════════════════════════════════

    def _pass_device(self):
        g      = self.game
        next_p = g.turn % 2
        self.pov = next_p

        modal = tk.Toplevel(self.root)
        modal.title("")
        modal.grab_set()
        modal.resizable(False, False)
        mw, mh = 380, 190
        modal.geometry(f"{mw}x{mh}+{self._scx(mw)}+{self._scy(mh)}")
        modal.configure(bg=DARK)

        tk.Label(modal, text=f"Pass to {g.names[next_p]}",
                 font=("Helvetica", 18, "bold"),
                 fg=GOLD, bg=DARK).pack(pady=(30, 10))
        tk.Label(modal, text="Hand is hidden — click when ready",
                 font=("Helvetica", 12), fg=WHITE, bg=DARK).pack()

        def _reveal():
            modal.destroy()
            self.msg = f"{g.names[self.pov]}'s turn."
            self._refresh()

        tk.Button(modal, text="  I'm ready  ",
                  font=("Helvetica", 12, "bold"),
                  bg=GOLD, fg=DARK, relief=tk.FLAT, cursor="hand2",
                  command=_reveal, pady=5).pack(pady=22)

    # ══ Winner ════════════════════════════════════════════════════════════════

    def _show_winner(self):
        g   = self.game
        p0c = sum(1 for t in g.totems if t.claimed == 0)
        p1c = sum(1 for t in g.totems if t.claimed == 1)
        
        # Save game if it was against AI
        if self.is_ai[1]:
            try:
                filepath = save_game(g, self.move_history, g.winner,
                                    initial_hands=self._initial_hands,
                                    initial_deck=self._initial_deck,
                                    training_moves=self.training_moves)
                print(f"Game saved to {filepath}")
            except Exception as e:
                print(f"Failed to save game: {e}")
        
        again = messagebox.askyesno(
            "Game Over",
            f"{g.names[g.winner]} wins!\n\n"
            f"{g.names[0]}: {p0c} totem(s)\n"
            f"{g.names[1]}: {p1c} totem(s)\n\n"
            "Play again?",
        )
        if again:
            self._start_screen()


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    root = tk.Tk()
    root.title("Battle Line")
    root.resizable(False, False)
    BattleLineGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
