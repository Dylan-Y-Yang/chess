"""
engine.py  –  python-chess board + improved αβ search
=====================================================

Public API (unchanged):
    • Board class
    • search_best_move(board, depth, side_white, time_limit)

Run `python engine.py` to execute the built-in test-suite.
"""

import time
import unittest
from collections import defaultdict

import chess

# ────────────────────────── configuration ──────────────────────────
SEARCH_DEPTH         = 10          # full-width plies the UI will ask for
TIME_LIMIT           = 20.0        # default seconds per move
INF                  = 10 ** 9
ASPIRATION_WINDOW    = 50          # centipawns initial aspiration half-window

PIECE_VALUES = {
    chess.PAWN:   100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK:   500,
    chess.QUEEN:  900,
    chess.KING:     0,
}

# ─────────────────── piece-square tables (mid-game) ──────────────────
def _mirror(idx: int) -> int:              # flip square for black
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

# ────────────────────────── Board wrapper ───────────────────────────
class Board:
    """Light wrapper around python-chess’s Board that exposes exactly the UI
    hooks the frontend already relies on so we can swap the engine pain-free."""
    def __init__(self) -> None:
        self._b: chess.Board = chess.Board()

    # ── helpers ─────────────────────────────────────────────────────
    def clone(self) -> "Board":
        clone = Board.__new__(Board)         # avoid __init__
        clone._b = self._b.copy()
        return clone

    def zobrist(self) -> int:
        # python-chess 1.x / 2.x compatibility
        if hasattr(self._b, "transposition_key"):
            return self._b.transposition_key()
        if hasattr(self._b, "zobrist_hash"):
            return self._b.zobrist_hash()
        return hash(self._b.fen())

    # ── UI integration ──────────────────────────────────────────────
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

    def generate_legal_moves(self, white_to_move: bool):
        moves = []
        for m in self._b.legal_moves:
            frm = (7 - m.from_square // 8, m.from_square % 8)
            to =  (7 - m.to_square   // 8, m.to_square   % 8)
            promo = chess.piece_symbol(m.promotion).upper() if m.promotion else None
            moves.append((frm, to, promo))
        return moves

    def is_in_check(self, white: bool) -> bool:
        return self._b.is_check()

    def make_move(self, move):
        frm, to, promo = move
        internal = chess.Move(
            (7 - frm[0]) * 8 + frm[1],
            (7 - to[0])  * 8 + to[1],
            promotion=chess.QUEEN if promo else None,
        )
        self._b.push(internal)

    # ── evaluation ──────────────────────────────────────────────────
    def evaluate(self) -> int:
        """Static evaluation (centipawns, + for White)."""
        score = 0
        for sq, p in self._b.piece_map().items():
            val = PIECE_VALUES[p.piece_type]
            val += PST[p.piece_type][sq if p.color else _mirror(sq)]
            score += val if p.color else -val
        return score

# ─────────────────────── search state (global) ──────────────────────
TT: dict[int, tuple[int, int, int, chess.Move | None]] = {}   # zobrist → (depth, flag, score, best_move)
TT_EX, TT_LO, TT_UP = 0, 1, 2

KILLERS: defaultdict[int, list[str]] = defaultdict(list)
HIST:    defaultdict[str, int]       = defaultdict(int)

_MVV = {chess.PAWN: 1, chess.KNIGHT: 2, chess.BISHOP: 3,
        chess.ROOK: 4, chess.QUEEN: 5, chess.KING: 6}

def _mvv_lva(move: chess.Move, bd: Board) -> int:
    """MVV-LVA ordering score."""
    if bd._b.is_en_passant(move):
        victim = chess.PAWN
    else:
        piece = bd._b.piece_at(move.to_square)
        if not piece:
            return 0
        victim = piece.piece_type
    attacker = bd._b.piece_at(move.from_square).piece_type
    return _MVV[victim] * 10 - _MVV[attacker]


def _ordered_moves(bd: Board, depth: int, tt_move: chess.Move | None):
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


# ──────────────────────── quiescence search ────────────────────────
def _quiesce(bd: Board, alpha: int, beta: int, deadline: float) -> int:
    if time.time() >= deadline:
        raise TimeoutError
    stand = bd.evaluate()
    if stand >= beta:
        return beta
    if stand > alpha:
        alpha = stand

    for move in bd._b.legal_moves:
        if not (bd._b.is_capture(move) or bd._b.gives_check(move)):
            continue
        child = bd.clone()
        child._b.push(move)
        score = -_quiesce(child, -beta, -alpha, deadline)
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
    return alpha


# ───────────────────────── negamax α-β ─────────────────────────────
def _alphabeta(
    bd: Board,
    depth: int,
    alpha: int,
    beta: int,
    deadline: float,
) -> int:
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

    # ── null-move pruning (skip if in check) ───────────────────────
    if depth >= 3 and not bd._b.is_check():
        null_bd = bd.clone()
        null_bd._b.push(chess.Move.null())
        if -_alphabeta(null_bd, depth - 3, -beta, -beta + 1, deadline) >= beta:
            return beta

    best_score = -INF
    best_move = None
    tt_move = entry[3] if entry else None

    for idx, move in enumerate(_ordered_moves(bd, depth, tt_move)):
        child = bd.clone()
        child._b.push(move)

        new_depth = depth - 1
        # Late Move Reduction
        if idx >= 4 and depth >= 3 and not bd._b.is_check():
            new_depth -= 1

        score = -_alphabeta(child, new_depth, -beta, -alpha, deadline)

        if score > best_score:
            best_score, best_move = score, move
        if score > alpha:
            alpha = score
        if alpha >= beta:
            kl = KILLERS[depth]
            if move.uci() not in kl:
                kl.insert(0, move.uci())
                KILLERS[depth] = kl[:2]
            break

    # history heuristic (quiet moves only)
    if best_move and not bd._b.is_capture(best_move):
        HIST[best_move.uci()] += depth * depth

    # store result in TT
    if best_move:
        if best_score <= alpha:
            flag = TT_UP
        elif best_score >= beta:
            flag = TT_LO
        else:
            flag = TT_EX
        TT[key] = (depth, flag, best_score, best_move)
    else:
        TT[key] = (depth, TT_EX, best_score, None)
    return best_score


# ───────────────────────── search driver ────────────────────────────
def search_best_move(
    bd: Board,
    depth: int = SEARCH_DEPTH,
    side_white: bool = True,
    time_limit: float = TIME_LIMIT,
):
    """
    Iterative deepening with aspiration windows and a hard time-limit.
    Returns UI-friendly ((r1,c1),(r2,c2),promo) or `None` on failure.
    """
    deadline = time.time() + time_limit
    best_move = None
    score = 0

    # fresh per-move heuristics, but keep the transposition table for reuse
    KILLERS.clear()
    HIST.clear()

    for d in range(1, depth + 1):
        window = ASPIRATION_WINDOW
        alpha = score - window
        beta = score + window

        while True:
            try:
                score = _alphabeta(bd.clone(), d, alpha, beta, deadline)
            except TimeoutError:
                # ran out of time – return best found so far
                if best_move:
                    return _to_ui_tuple(best_move)
                return None

            if score <= alpha:
                alpha -= window
            elif score >= beta:
                beta += window
            else:
                break  # within window – good

        entry = TT.get(bd.zobrist())
        if entry:
            best_move = entry[3]

        if time.time() >= deadline:
            break

    return _to_ui_tuple(best_move) if best_move else None


# ──────────────────────── helpers (UI format) ───────────────────────
def _to_ui_tuple(chess_move: chess.Move | None):
    if chess_move is None:
        return None
    frm = (7 - chess_move.from_square // 8, chess_move.from_square % 8)
    to  = (7 - chess_move.to_square   // 8, chess_move.to_square   % 8)
    promo = chess.piece_symbol(chess_move.promotion).upper() if chess_move.promotion else None
    return (frm, to, promo)


# ────────────────────────── unit tests ──────────────────────────────
class EngineTests(unittest.TestCase):
    def test_static_eval_symmetry(self):
        """Value should flip sign when the same material is mirrored."""
        b1 = Board()
        b1._b.set_fen("8/8/8/8/8/8/4r3/4Q3 w - - 0 1")  # Q vs r – White better
        b2 = Board()
        b2._b.set_fen("8/4q3/8/8/8/8/8/4R3 b - - 0 1")  # mirrored – Black better
        self.assertEqual(b1.evaluate(), -b2.evaluate())

    def test_best_move_is_legal(self):
        board = Board()
        move = search_best_move(board, depth=2, time_limit=1.0)
        self.assertIsNotNone(move)
        self.assertIn(move, board.generate_legal_moves(True))

    def test_respects_time_limit(self):
        board = Board()
        start = time.time()
        _ = search_best_move(board, depth=SEARCH_DEPTH, time_limit=0.1)
        self.assertLessEqual(time.time() - start, 0.2)

    def test_transposition_table_reuse(self):
        global TT
        TT.clear()
        b = Board()
        search_best_move(b, depth=2, time_limit=1.0)
        size1 = len(TT)
        search_best_move(b, depth=3, time_limit=1.0)
        self.assertGreaterEqual(len(TT), size1)


# ────────────────────────── self-test hook ──────────────────────────
if __name__ == "__main__":
    unittest.main()
