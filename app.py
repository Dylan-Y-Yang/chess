"""
app.py – FastAPI backend for Chess Bot
"""

from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from engine import Board, search_best_move

TIME_LIMIT   = 20.0      # seconds per bot turn
DEFAULT_DEPTH = 10

app = FastAPI()

app.mount("/static",  StaticFiles(directory="static"),               name="static")
app.mount("/assets",  StaticFiles(directory="frontend/dist/assets"), name="assets")

@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/game")

@app.get("/game", response_class=HTMLResponse)
def game_page():
    return FileResponse("frontend/dist/index.html")

# -------------- global game state --------------
board          = Board()
white_to_move  = True
player_is_white = True

# -------------- helpers --------------
def sq_to_rc(s): return 8 - int(s[1]), ord(s[0]) - 97
def rc_to_sq(rc): r, c = rc; return f"{chr(c + 97)}{8 - r}"

class MoveReq(BaseModel):
    from_square: str
    to_square:   str
    promotion:   Optional[str] = None

class NewGameReq(BaseModel):
    player_white: bool = True
    depth: int = DEFAULT_DEPTH

class DepthReq(BaseModel):
    depth: int = DEFAULT_DEPTH

# -------------- endpoints --------------
@app.post("/newgame")
def new_game(req: NewGameReq):
    global board, white_to_move, player_is_white
    board          = Board()
    white_to_move  = True
    player_is_white = req.player_white

    # if player chose Black, let bot (White) move immediately
    if not player_is_white:
        bot_move_internal(req.depth)

    return {
        "board": board.board,
        "white_to_move": white_to_move,
        "check": False,
        "checkmate": False,
        "stalemate": False,
    }

@app.get("/legal_moves")
def legal(from_square: str):
    src = sq_to_rc(from_square)
    moves = [
        {"to": rc_to_sq(m[1]), "promotion": m[2]}
        for m in board.generate_legal_moves(white_to_move)
        if m[0] == src
    ]
    return {"moves": moves}

@app.post("/move")
def human_move(req: MoveReq):
    global board, white_to_move

    # ★ reject if it's not the player's turn
    if player_is_white != white_to_move:
        raise HTTPException(400, "It is not your turn")

    mv = (sq_to_rc(req.from_square), sq_to_rc(req.to_square), req.promotion)
    if mv not in board.generate_legal_moves(white_to_move):
        raise HTTPException(400, "Illegal move")

    board.make_move(mv)
    white_to_move = not white_to_move

    in_check  = board.is_in_check(white_to_move)
    legal_now = board.generate_legal_moves(white_to_move)
    return {
        "board":        board.board,
        "white_to_move": white_to_move,
        "check":        in_check,
        "checkmate":    in_check and not legal_now,
        "stalemate":    (not in_check) and (not legal_now),
        "bot_needed":   bool(legal_now) and (white_to_move != player_is_white),
    }


def bot_move_internal(depth: int):
    global board, white_to_move
    bot_mv = search_best_move(
        board,
        depth=depth,
        side_white=white_to_move,
        time_limit=TIME_LIMIT,
    )
    if bot_mv:
        board.make_move(bot_mv)
        white_to_move = not white_to_move

@app.post("/bot_move")
def bot_move(req: DepthReq):
    if player_is_white == white_to_move:
        raise HTTPException(400, "It is not the bot's turn")

    bot_move_internal(req.depth)

    in_check = board.is_in_check(white_to_move)
    legal_now = board.generate_legal_moves(white_to_move)

    return {
        "board":       board.board,
        "white_to_move": white_to_move,
        "check":       in_check,
        "checkmate":   in_check and not legal_now,
        "stalemate":   (not in_check) and (not legal_now),
    }
