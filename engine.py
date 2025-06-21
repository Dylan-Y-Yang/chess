"""
engine.py  –  multiprocessing αβ search (PSTs imported from pst.py)
"""

from __future__ import annotations

import multiprocessing as mp
import time
from collections import defaultdict

import chess
from pst import PST                           # ← piece-square tables live here

# ───────── configuration ─────────
SEARCH_DEPTH   = 10
TIME_LIMIT     = 20.0        # seconds / turn
PROCESSES      = 24           # worker processes for root split (set 1 to disable)
INF            = 10 ** 9

PIECE_VALUES = {
    chess.PAWN:   100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK:   500,
    chess.QUEEN:  900,
    chess.KING:     0,
}

def _mirror(idx: int) -> int:           # flip square for Black
    return idx ^ 56

# ───────── Board wrapper ─────────
class Board:
    def __init__(self):
        self._b = chess.Board()

    def clone(self) -> "Board":
        c = Board.__new__(Board)
        c._b = self._b.copy()
        return c

    def zobrist(self) -> int:
        if hasattr(self._b, "transposition_key"):
            return self._b.transposition_key()
        if hasattr(self._b, "zobrist_hash"):
            return self._b.zobrist_hash()
        return hash(self._b.fen())

    # ----- UI helpers --------------------------------------------------
    @property
    def board(self):
        rows = []
        for rank in range(7, -1, -1):
            row = []
            for file in range(8):
                p = self._b.piece_at(chess.square(file, rank))
                row.append(p.symbol() if p else ".")
            rows.append(row)
        return rows

    def generate_legal_moves(self, white_to_move):
        out = []
        for m in self._b.legal_moves:
            frm = (7 - m.from_square // 8, m.from_square % 8)
            to  = (7 - m.to_square   // 8, m.to_square   % 8)
            promo = chess.piece_symbol(m.promotion).upper() if m.promotion else None
            out.append((frm, to, promo))
        return out

    def is_in_check(self, white) -> bool:
        return self._b.is_check()

    def make_move(self, ui_move):
        frm, to, promo = ui_move
        promo_piece = {"Q": chess.QUEEN, "R": chess.ROOK,
                       "B": chess.BISHOP, "N": chess.KNIGHT}.get(promo, None)
        self._b.push(chess.Move(
            (7 - frm[0]) * 8 + frm[1],
            (7 - to[0])  * 8 + to[1],
            promotion=promo_piece,
        ))

    # ----- static evaluation (+ for White) ----------------------------
    def evaluate(self) -> int:
        score = 0
        for sq, p in self._b.piece_map().items():
            v = PIECE_VALUES[p.piece_type] + PST[p.piece_type][sq if p.color else _mirror(sq)]
            score += v if p.color else -v
        # small mobility term (1 cp per legal move)
        mob = len(list(self._b.legal_moves))
        score += mob if self._b.turn else -mob
        return score

# ───────── local search data ─────────
TT: dict[int, tuple[int, int, int, chess.Move | None]] = {}
TT_EX, TT_LO, TT_UP = 0, 1, 2
KILLERS = defaultdict(list)
HIST    = defaultdict(int)

_MVV = {chess.PAWN: 1, chess.KNIGHT: 2, chess.BISHOP: 3,
        chess.ROOK: 4, chess.QUEEN: 5, chess.KING: 6}

def _mvv_lva(m: chess.Move, bd: Board) -> int:
    if bd._b.is_en_passant(m):
        victim = chess.PAWN
    else:
        pc = bd._b.piece_at(m.to_square)
        if not pc:
            return 0
        victim = pc.piece_type
    attacker = bd._b.piece_at(m.from_square).piece_type
    return _MVV[victim] * 10 - _MVV[attacker]

def _ordered_moves(bd: Board, depth: int, tt_move):
    moves = list(bd._b.legal_moves)
    moves.sort(
        key=lambda m: (
            m == tt_move,
            _mvv_lva(m, bd),
            m.uci() in KILLERS[depth],
            HIST[m.uci()],
        ),
        reverse=True,
    )
    return moves

# ───────── quiescence ─────────
def _quiesce(bd: Board, alpha: int, beta: int, deadline: float) -> int:
    if time.time() >= deadline:
        raise TimeoutError
    stand = bd.evaluate()
    stand *= 1 if bd._b.turn == chess.WHITE else -1
    if stand >= beta:
        return beta
    if stand > alpha:
        alpha = stand

    for m in bd._b.legal_moves:
        if not (bd._b.is_capture(m) or bd._b.gives_check(m)):
            continue
        child = bd.clone()
        child._b.push(m)
        val = -_quiesce(child, -beta, -alpha, deadline)
        if val >= beta:
            return beta
        if val > alpha:
            alpha = val
    return alpha

# ───────── recursive αβ ─────────
def _alphabeta(bd: Board, depth: int, alpha: int, beta: int, deadline: float) -> int:
    if time.time() >= deadline:
        raise TimeoutError

    key = bd.zobrist()
    entry = TT.get(key)
    if entry and entry[0] >= depth:
        flag, score = entry[1], entry[2]
        if flag == TT_EX:
            return score
        if flag == TT_LO and score >= beta:
            return score
        if flag == TT_UP and score <= alpha:
            return score

    if depth == 0:
        return _quiesce(bd, alpha, beta, deadline)

    # guarded null-move pruning
    skip_null = bd._b.is_check() or bd._b.has_legal_en_passant()
    if depth >= 3 and not skip_null:
        null_bd = bd.clone()
        null_bd._b.push(chess.Move.null())
        if -_alphabeta(null_bd, depth - 3, -beta, -beta + 1, deadline) >= beta:
            return beta

    best_score = -INF
    best_move  = None
    tt_move    = entry[3] if entry else None
    orig_alpha, orig_beta = alpha, beta

    for idx, m in enumerate(_ordered_moves(bd, depth, tt_move)):
        child = bd.clone()
        child._b.push(m)

        new_depth = depth - 1
        # safer LMR: activate later & deeper
        if idx >= 6 and depth >= 5 and not bd._b.is_check():
            new_depth -= 1

        score = -_alphabeta(child, new_depth, -beta, -alpha, deadline)

        if score > best_score:
            best_score, best_move = score, m
        if score > alpha:
            alpha = score
        if alpha >= beta:
            killers = KILLERS[depth]
            if m.uci() not in killers:
                killers.insert(0, m.uci())
                KILLERS[depth] = killers[:2]
            break

    if best_move and not bd._b.is_capture(best_move):
        HIST[best_move.uci()] += depth * depth

    flag = TT_EX
    if best_score <= orig_alpha:
        flag = TT_UP
    elif best_score >= orig_beta:
        flag = TT_LO
    TT[key] = (depth, flag, best_score, best_move)
    return best_score

# ───────── worker for process pool ─────────
def _score_child(args):
    fen, depth, deadline = args
    bd = Board()
    bd._b.set_fen(fen)
    try:
        score = _alphabeta(bd, depth, -INF, INF, deadline)
    except TimeoutError:
        score = -INF
    return score

# ───────── public driver ─────────
def search_best_move(
    bd: Board,
    depth: int = SEARCH_DEPTH,
    side_white: bool = True,
    time_limit: float = TIME_LIMIT,
    processes: int = PROCESSES,
):
    deadline = time.time() + time_limit
    root_moves = list(bd._b.legal_moves)
    if not root_moves:
        return None

    child_fens = []
    for m in root_moves:
        child = bd.clone()
        child._b.push(m)
        child_fens.append(child._b.fen())

    best_score, best_move = -INF, None

    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=processes) as pool:
        for d in range(1, depth + 1):
            scores = pool.map(
                _score_child,
                [(fen, d - 1, deadline) for fen in child_fens],
                chunksize=1,
            )
            for score, m in zip(scores, root_moves):
                score = -score    
                if score > best_score:
                    best_score, best_move = score, m
            if time.time() >= deadline:
                break

    return _to_ui(best_move)

# ───────── helper: engine move → UI tuple ─────────
def _to_ui(m: chess.Move | None):
    if m is None:
        return None
    frm = (7 - m.from_square // 8, m.from_square % 8)
    to  = (7 - m.to_square   // 8, m.to_square   % 8)
    promo = chess.piece_symbol(m.promotion).upper() if m.promotion else None
    return (frm, to, promo)
