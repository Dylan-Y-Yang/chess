"""
engine.py  –  python-chess board + improved negamax αβ
======================================================

Public API (unchanged):
    • Board class
    • search_best_move(board, depth, side_white, time_limit)

Run `python engine.py` to execute the built-in unit tests.
"""

import time
import unittest
from collections import defaultdict
import chess

# ───────────────────────── configuration ──────────────────────────
SEARCH_DEPTH   = 10       # default plies if caller omits depth
TIME_LIMIT     = 20.0     # seconds per move
INF            = 10 ** 9
ASP_WINDOW     = 50       # aspiration half-window (centipawns)

PIECE_VALUES = {
    chess.PAWN:   100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK:   500,
    chess.QUEEN:  900,
    chess.KING:     0,
}

# ─────────────── piece-square tables (mid-game) ───────────────────
def _mirror(idx: int) -> int:          # flip square for Black
    return idx ^ 56

PST = {
    chess.PAWN: [
         0,  5,  5,-10,-10,  5,  5,  0,
         0, 10, -5,  0,  0, -5, 10,  0,
         0, 10, 10, 20, 20, 10, 10,  0,
         5, 15, 15, 25, 25, 15, 15,  5,
        10, 20, 20, 30, 30, 20, 20, 10,
        20, 30, 30, 40, 40, 30, 30, 20,
         0,  0,  0,  0,  0,  0,  0,  0,
         0,  0,  0,  0,  0,  0,  0,  0],
    chess.KNIGHT: [
        -50,-40,-30,-30,-30,-30,-40,-50,
        -40,-20,  0,  0,  0,  0,-20,-40,
        -30,  5, 10, 15, 15, 10,  5,-30,
        -30,  0, 15, 20, 20, 15,  0,-30,
        -30,  5, 15, 20, 20, 15,  5,-30,
        -30,  0, 10, 15, 15, 10,  0,-30,
        -40,-20,  0,  0,  0,  0,-20,-40,
        -50,-40,-30,-30,-30,-30,-40,-50],
    chess.BISHOP: [
        -20,-10,-10,-10,-10,-10,-10,-20,
        -10,  5,  0,  0,  0,  0,  5,-10,
        -10, 10, 10, 10, 10, 10, 10,-10,
        -10,  0, 10, 15, 15, 10,  0,-10,
        -10,  5, 10, 15, 15, 10,  5,-10,
        -10, 10, 10, 10, 10, 10, 10,-10,
        -10,  5,  0,  0,  0,  0,  5,-10,
        -20,-10,-10,-10,-10,-10,-10,-20],
    chess.ROOK: [
          0,  0,  5, 10, 10,  5,  0,  0,
         -5,  0,  0,  0,  0,  0,  0, -5,
         -5,  0,  0,  0,  0,  0,  0, -5,
         -5,  0,  0,  5,  5,  0,  0, -5,
         -5,  0,  0,  5,  5,  0,  0, -5,
         -5,  0,  0,  0,  0,  0,  0, -5,
          5, 10, 10, 10, 10, 10, 10,  5,
          0,  0,  0,  0,  0,  0,  0,  0],
    chess.QUEEN: [
        -20,-10,-10, -5, -5,-10,-10,-20,
        -10,  0,  0,  0,  0,  0,  0,-10,
        -10,  0,  5,  5,  5,  5,  0,-10,
         -5,  0,  5,  5,  5,  5,  0, -5,
          0,  0,  5,  5,  5,  5,  0, -5,
        -10,  5,  5,  5,  5,  5,  0,-10,
        -10,  0,  5,  0,  0,  0,  0,-10,
        -20,-10,-10, -5, -5,-10,-10,-20],
    chess.KING: [
        -30,-40,-40,-50,-50,-40,-40,-30,
        -30,-40,-40,-50,-50,-40,-40,-30,
        -30,-40,-40,-50,-50,-40,-40,-30,
        -30,-40,-40,-50,-50,-40,-40,-30,
        -20,-30,-30,-40,-40,-30,-30,-20,
        -10,-20,-20,-20,-20,-20,-20,-10,
         20, 20,  0,  0,  0,  0, 20, 20,
         20, 30, 10,  0,  0, 10, 30, 20],
}

# ───────────────────── Board wrapper ──────────────────────
class Board:
    """Thin wrapper around python-chess Board with UI-friendly helpers."""
    def __init__(self):
        self._b = chess.Board()

    def clone(self):
        c = Board.__new__(Board)
        c._b = self._b.copy()
        return c

    def zobrist(self):
        if hasattr(self._b, "transposition_key"):
            return self._b.transposition_key()
        if hasattr(self._b, "zobrist_hash"):
            return self._b.zobrist_hash()
        return hash(self._b.fen())

    # ── UI helpers ───────────────────────────────────────
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
        moves = []
        for m in self._b.legal_moves:
            frm = (7 - m.from_square // 8, m.from_square % 8)
            to  = (7 - m.to_square   // 8, m.to_square   % 8)
            promo = chess.piece_symbol(m.promotion).upper() if m.promotion else None
            moves.append((frm, to, promo))
        return moves

    def is_in_check(self, white):
        return self._b.is_check()

    def make_move(self, ui_move):
        """Apply a UI move tuple ((r1,c1),(r2,c2),promo)."""
        frm, to, promo = ui_move

        # map 'Q','R','B','N' → python-chess constants
        promo_piece = None
        if promo:
            promo_piece = {
                "Q": chess.QUEEN,
                "R": chess.ROOK,
                "B": chess.BISHOP,
                "N": chess.KNIGHT,
            }.get(promo.upper(), chess.QUEEN)

        move = chess.Move(
            (7 - frm[0]) * 8 + frm[1],
            (7 - to[0])  * 8 + to[1],
            promotion=promo_piece,
        )
        self._b.push(move)

    # ── static evaluation (+ for White) ───────────────────
    def evaluate(self):
        score = 0
        for sq, p in self._b.piece_map().items():
            v = PIECE_VALUES[p.piece_type]
            v += PST[p.piece_type][sq if p.color else _mirror(sq)]
            score += v if p.color else -v
        return score

# ───────────────────── search state ──────────────────────
TT: dict[int, tuple[int, int, int, chess.Move | None]] = {}
TT_EX, TT_LO, TT_UP = 0, 1, 2

KILLERS: defaultdict[int, list[str]] = defaultdict(list)
HIST:    defaultdict[str, int]       = defaultdict(int)

_MVV = {chess.PAWN: 1, chess.KNIGHT: 2, chess.BISHOP: 3,
        chess.ROOK: 4, chess.QUEEN: 5, chess.KING: 6}

def _mvv_lva(m: chess.Move, bd: Board) -> int:
    if bd._b.is_en_passant(m):
        victim = chess.PAWN
    else:
        piece = bd._b.piece_at(m.to_square)
        if not piece:
            return 0
        victim = piece.piece_type
    attacker = bd._b.piece_at(m.from_square).piece_type
    return _MVV[victim] * 10 - _MVV[attacker]

def _ordered_moves(bd: Board, depth: int, tt_move):
    ms = list(bd._b.legal_moves)
    ms.sort(
        key=lambda m: (
            m == tt_move,
            _mvv_lva(m, bd),
            m.uci() in KILLERS[depth],
            HIST[m.uci()],
        ),
        reverse=True,
    )
    return ms

# ───────────────────── quiescence search ─────────────────────
def _quiesce(bd: Board, alpha: int, beta: int, deadline: float) -> int:
    if time.time() >= deadline:
        raise TimeoutError
    stand = bd.evaluate()
    stand *= 1 if bd._b.turn == chess.WHITE else -1   # side-to-move fix

    if stand >= beta:
        return beta
    if stand > alpha:
        alpha = stand

    for m in bd._b.legal_moves:
        if not (bd._b.is_capture(m) or bd._b.gives_check(m)):
            continue
        child = bd.clone()
        child._b.push(m)
        scor = -_quiesce(child, -beta, -alpha, deadline)
        if scor >= beta:
            return beta
        if scor > alpha:
            alpha = scor
    return alpha

# ───────────────────── negamax αβ───────────────────────────
def _alphabeta(bd: Board, depth: int, alpha: int, beta: int, deadline: float) -> int:
    if time.time() >= deadline:
        raise TimeoutError

    key   = bd.zobrist()
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

    # null-move pruning
    if depth >= 3 and not bd._b.is_check():
        nm_bd = bd.clone()
        nm_bd._b.push(chess.Move.null())
        if -_alphabeta(nm_bd, depth - 3, -beta, -beta + 1, deadline) >= beta:
            return beta

    best_score = -INF
    best_move  = None
    tt_move    = entry[3] if entry else None
    orig_alpha, orig_beta = alpha, beta

    for idx, m in enumerate(_ordered_moves(bd, depth, tt_move)):
        child = bd.clone()
        child._b.push(m)

        d2 = depth - 1
        if idx >= 4 and depth >= 3 and not bd._b.is_check():
            d2 -= 1          # late move reduction

        sc = -_alphabeta(child, d2, -beta, -alpha, deadline)

        if sc > best_score:
            best_score, best_move = sc, m
        if sc > alpha:
            alpha = sc
        if alpha >= beta:
            k = KILLERS[depth]
            if m.uci() not in k:
                k.insert(0, m.uci())
                KILLERS[depth] = k[:2]
            break

    # history heuristic
    if best_move and not bd._b.is_capture(best_move):
        HIST[best_move.uci()] += depth * depth

    # store in TT
    if best_move:
        if best_score <= orig_alpha:
            flag = TT_UP
        elif best_score >= orig_beta:
            flag = TT_LO
        else:
            flag = TT_EX
        TT[key] = (depth, flag, best_score, best_move)
    else:
        TT[key] = (depth, TT_EX, best_score, None)
    return best_score

# ───────────────────── driver ────────────────────────
def search_best_move(
    bd: Board,
    depth: int = SEARCH_DEPTH,
    side_white: bool = True,
    time_limit: float = TIME_LIMIT,
):
    deadline  = time.time() + time_limit
    best_move = None
    score     = 0

    KILLERS.clear()
    HIST.clear()

    for d in range(1, depth + 1):
        window = ASP_WINDOW
        alpha  = score - window
        beta   = score + window

        while True:
            try:
                score = _alphabeta(bd.clone(), d, alpha, beta, deadline)
            except TimeoutError:
                return _to_ui(best_move)
            if score <= alpha:
                alpha -= window
            elif score >= beta:
                beta += window
            else:
                break

        entry = TT.get(bd.zobrist())
        if entry:
            best_move = entry[3]

        if time.time() >= deadline:
            break

    return _to_ui(best_move)

# ───────────────────── helper ─────────────────────────
def _to_ui(m: chess.Move | None):
    if m is None:
        return None
    frm = (7 - m.from_square // 8, m.from_square % 8)
    to  = (7 - m.to_square   // 8, m.to_square   % 8)
    promo = chess.piece_symbol(m.promotion).upper() if m.promotion else None
    return (frm, to, promo)

# ───────────────────── unit tests ─────────────────────
class EngineTests(unittest.TestCase):
    def test_eval_sign(self):
        b1 = Board()
        b1._b.set_fen("8/8/8/8/8/8/4r3/4Q3 w - - 0 1")
        b2 = Board()
        b2._b.set_fen("8/4q3/8/8/8/8/8/4R3 b - - 0 1")
        self.assertEqual(b1.evaluate(), -b2.evaluate())

    def test_side_to_move(self):
        b = Board()
        b._b.set_fen("8/8/8/8/8/8/4r3/4Q3 w - - 0 1")
        v1 = _quiesce(b, -INF, INF, time.time() + 1)
        b._b.turn = chess.BLACK
        v2 = _quiesce(b, -INF, INF, time.time() + 1)
        self.assertLess(v1, 0)  # Black to move & down material
        self.assertGreater(v2, 0)

    def test_engine_returns_legal(self):
        b = Board()
        mv = search_best_move(b, depth=2, time_limit=1.0)
        self.assertIn(mv, b.generate_legal_moves(True))

if __name__ == "__main__":
    unittest.main()
