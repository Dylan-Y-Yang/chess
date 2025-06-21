"""
app.py – FastAPI backend for Chess Bot
-------------------------------------
• If the bot starts as White it plays one random first move from:
  1.e4, 1.d4, 1.c4, 1.Nf3, or 1.Nc3
"""

import threading, random
from typing import Optional

import chess               # ←── missing import fixed
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from engine import Board, search_best_move

# ───────── configuration ─────────
TIME_LIMIT    = 20.0
DEFAULT_DEPTH = 10

app = FastAPI()
app.mount("/static",  StaticFiles(directory="static"),               name="static")
app.mount("/assets",  StaticFiles(directory="frontend/dist/assets"), name="assets")

# ───────── global state ─────────
board           = Board()
white_to_move   = True
player_is_white = True
lock            = threading.RLock()

# ───────── helpers ─────────
def sq_to_rc(s): return 8 - int(s[1]), ord(s[0]) - 97
def rc_to_sq(rc): r, c = rc; return f"{chr(c+97)}{8-r}"

class MoveReq(BaseModel):
    from_square: str
    to_square:   str
    promotion:   Optional[str] = None

class NewGameReq(BaseModel):
    player_white: bool = True
    depth: int = DEFAULT_DEPTH

class DepthReq(BaseModel):
    depth: int = DEFAULT_DEPTH

# ───────── routes ─────────
@app.get("/", include_in_schema=False)
def root(): return RedirectResponse("/game")

@app.get("/game", response_class=HTMLResponse)
def game_page(): return FileResponse("frontend/dist/index.html")

@app.post("/newgame")
def new_game(req: NewGameReq):
    """Start a new game.  
       If the human chooses Black, the bot immediately plays a random
       first move (e4 / d4 / c4 / Nf3 / Nc3)."""
    global board, white_to_move, player_is_white
    with lock:
        board, white_to_move = Board(), True
        player_is_white = req.player_white

        if not player_is_white:             
            _bot_opening_or_search(req.depth)

        return _state()

@app.get("/legal_moves")
def legal_moves(from_square: str):
    src = sq_to_rc(from_square)
    moves = [{"to": rc_to_sq(m[1]), "promotion": m[2]}
             for m in board.generate_legal_moves(white_to_move) if m[0] == src]
    return {"moves": moves}

@app.post("/move")
def human_move(req: MoveReq):
    global white_to_move
    with lock:
        if player_is_white != white_to_move:
            raise HTTPException(400, "It is not your turn")

        mv = (sq_to_rc(req.from_square), sq_to_rc(req.to_square), req.promotion)
        if mv not in board.generate_legal_moves(white_to_move):
            raise HTTPException(400, "Illegal move")

        board.make_move(mv)
        white_to_move = not white_to_move

        st = _state()
        st["bot_needed"] = (not st["draw"]) and (white_to_move != player_is_white) and st["legal_moves"]
        return st

@app.post("/bot_move")
def bot_move(req: DepthReq):
    with lock:
        if player_is_white == white_to_move:
            raise HTTPException(400, "Not bot's turn")
        _bot_move_search(req.depth)
        return _state()

# ───────── bot helpers ─────────
OPENING_UCIS = ["e2e4", "d2d4", "c2c4", "g1f3", "b1c3"]

def _bot_opening_or_search(depth: int):
    """Random first move if game just started, otherwise normal search."""
    global white_to_move
    if len(board._b.move_stack) == 0 and board._b.turn == chess.WHITE:
        board._b.push(chess.Move.from_uci(random.choice(OPENING_UCIS)))
        white_to_move = False
    else:
        _bot_move_search(depth)

def _bot_move_search(depth: int):
    global white_to_move
    mv = search_best_move(board, depth=depth, side_white=white_to_move, time_limit=TIME_LIMIT)
    if mv and mv in board.generate_legal_moves(white_to_move):
        board.make_move(mv)
        white_to_move = not white_to_move

# ───────── state builder ─────────
def _state():
    in_check = board.is_in_check(white_to_move)
    legal    = board.generate_legal_moves(white_to_move)
    return {
        "board":        board.board,
        "white_to_move": white_to_move,
        "check":        in_check,
        "checkmate":    in_check and not legal,
        "stalemate":    (not in_check) and (not legal),
        "draw":         board._b.is_repetition(3) or board._b.can_claim_fifty_moves(),
        "legal_moves":  legal,
    }
