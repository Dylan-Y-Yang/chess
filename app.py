# app.py  – two-step move handling

from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from engine import Board, search_best_move

DEPTH      = 10      # fixed search depth
TIME_LIMIT = 20.0    # seconds per bot move

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/assets", StaticFiles(directory="frontend/dist/assets"), name="assets")

@app.get("/", include_in_schema=False)
def root(): return RedirectResponse("/game")

@app.get("/game", response_class=HTMLResponse)
def game_page(): return FileResponse("frontend/dist/index.html")

board = Board()
white_to_move = True   # True = White

# ---------- helpers ----------
def sq_to_rc(s): return 8-int(s[1]), ord(s[0])-97
def rc_to_sq(rc): r,c = rc; return f"{chr(c+97)}{8-r}"

class MoveReq(BaseModel):
    from_square: str
    to_square: str
    promotion: Optional[str] = None

# ---------- game endpoints ----------
@app.post("/newgame")
def new_game():
    global board, white_to_move
    board = Board()
    white_to_move = True
    return {"board": board.board, "white_to_move": white_to_move}

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
    """
    Apply the player's move only.  The client then calls /bot_move.
    """
    global board, white_to_move
    src, dst = sq_to_rc(req.from_square), sq_to_rc(req.to_square)
    move = (src, dst, req.promotion)

    if move not in board.generate_legal_moves(white_to_move):
        raise HTTPException(400, "Illegal move")

    board.make_move(move)
    white_to_move = not white_to_move

    in_check = board.is_in_check(white_to_move)
    legal    = board.generate_legal_moves(white_to_move)
    bot_needed = bool(legal)            # bot has moves to play

    return {
        "board": board.board,
        "white_to_move": white_to_move,
        "check": in_check,
        "checkmate": in_check and not legal,
        "bot_needed": bot_needed
    }

@app.post("/bot_move")
def bot_move():
    """
    Engine searches and applies its move.  Must be called only if it is
    the engine's turn (white_to_move indicates that).
    """
    global board, white_to_move
    bot = search_best_move(board, DEPTH, side_white=white_to_move, time_limit=TIME_LIMIT)
    if not bot:
        raise HTTPException(400, "No legal moves for bot")

    board.make_move(bot)
    white_to_move = not white_to_move

    in_check   = board.is_in_check(white_to_move)
    legal_next = board.generate_legal_moves(white_to_move)
    mate       = in_check and not legal_next

    return {
        "board": board.board,
        "bot_move": {
            "from": rc_to_sq(bot[0]),
            "to":   rc_to_sq(bot[1]),
            "promotion": bot[2]
        },
        "white_to_move": white_to_move,
        "check": in_check,
        "checkmate": mate
    }
