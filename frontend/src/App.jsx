import React, { useEffect, useState } from "react";
import axios from "axios";

import Board from "./components/Board";
import Controls from "./components/Controls";
import PromotionModal from "./components/PromotionModal";

/* -------- music -------- */
const bg = (() => {
    const a = new Audio("/static/background.mp3");
    a.loop = true;
    a.volume = 0.2;
    return a;
})();

/* -------- one-shot SFX -------- */
const SFX = {
    select: "/static/select.mp3",
    move: "/static/move.mp3",
    check: "/static/check.mp3",
    mate: "/static/mate.mp3",
};
function playSfx(name, vol = 1) {
    const a = new Audio(SFX[name]);
    a.volume = vol;
    a.play().catch(() => { });
}

/* -------- helpers -------- */
const files = "abcdefgh";
const ranks = "12345678";
const f2c = (f) => files.indexOf(f);
const r2row = (r) => 8 - +r;
const sq2rc = (sq) => [r2row(sq[1]), f2c(sq[0])];

export default function App() {
    const [board, setBoard] = useState([]);
    const [white, setWhite] = useState(true);
    const [sel, setSel] = useState(null);
    const [legal, setLegal] = useState([]);
    const [check, setCheck] = useState(false);
    const [mate, setMate] = useState(false);
    const [stalemate, setStalemate] = useState(false);
    const [promo, setPromo] = useState(null);

    const [playMusic, setPlayMusic] = useState(false);
    const [vol, setVol] = useState(0.2);
    const [depth, setDepth] = useState(3);
    const [playAsWhite, setPlayAsWhite] = useState(true);   // ← side picker

    /* ---------------- music toggle ---------------- */
    useEffect(() => {
        bg.volume = vol;
        playMusic ? bg.play().catch(() => { }) : bg.pause();
    }, [playMusic, vol]);

    /* -------------- start / restart game -------------- */
    async function newGame() {
        const r = await axios.post("/newgame", { player_white: playAsWhite, depth });
        applyServerState(r);
    }

    /* ★ automatically restart when side choice changes */
    useEffect(() => { newGame(); }, [playAsWhite]);

    /* and once at first mount */
    useEffect(() => { newGame(); }, []);              // initial mount

    /* -------- square click -------- */
    async function onSquareClick(sq) {
        if (promo) return;
        const [r, c] = sq2rc(sq);

        /* first click = select piece */
        if (!sel) {
            const piece = board[r][c];

            /* must click our own colour */
            const isWhitePiece = piece === piece.toUpperCase();
            if ((playAsWhite && !isWhitePiece) || (!playAsWhite && isWhitePiece))
                return;

            /* must be our turn */
            if (white !== playAsWhite) return;

            playSfx("select", vol);
            setSel(sq);
            try {
                const lm = await axios.get("/legal_moves", { params: { from_square: sq } });
                setLegal(lm.data.moves);
            } catch { setLegal([]); }
            return;
        }

        /* second click = attempt move */
        const mv = legal.find((m) => m.to === sq);
        if (!mv) { setSel(null); setLegal([]); return; }

        if (mv.promotion) { setPromo({ from: sel, to: sq }); return; }
        await pushPlayerMove(sel, sq, null);
    }

    /* -------- push move, maybe bot -------- */
    async function pushPlayerMove(from, to, prom) {
        let res;
        try {
            res = await axios.post("/move", { from_square: from, to_square: to, promotion: prom });
        } catch (err) { console.error(err); return; }
        playSfx("move", vol);
        applyServerState(res);

        if (res.data.bot_needed) {
            try {
                const bot = await axios.post("/bot_move", { depth });
                playSfx("move", vol);
                applyServerState(bot);
            } catch (err) { console.error(err); }
        }
    }

    /* -------- server → state -------- */
    function applyServerState(res) {
        const d = res.data;
        setBoard(d.board);
        setWhite(d.white_to_move);

        if (d.checkmate) { setMate(true); setStalemate(false); playSfx("mate", vol); }
        else if (d.stalemate) { setStalemate(true); setMate(false); playSfx("mate", vol); }
        else { setMate(false); setStalemate(false); }

        if (d.check) { setCheck(true); playSfx("check", vol); }
        else { setCheck(false); }

        setSel(null); setLegal([]); setPromo(null);
    }

    /* ---------------- render ---------------- */
    return (
        <>
            <h1 style={{ textAlign: "center" }}>Chess Bot</h1>

            <Controls
                onNewGame={newGame}
                playAsWhite={playAsWhite}
                onSideChange={setPlayAsWhite}
                sideToMove={white ? "White" : "Black"}
                musicPlaying={playMusic}
                onToggleMusic={() => setPlayMusic((p) => !p)}
                volume={vol}
                onVolumeChange={setVol}
                depth={depth}
                onDepthChange={setDepth}
            />

            <Board
                board={board}
                selected={sel}
                legalMoves={legal.map((m) => m.to)}
                onSquareClick={onSquareClick}
                flip={!playAsWhite}            /* ★ flip board if playing Black */
            />

            {(mate || stalemate) && (
                <div className="overlay">
                    <h2>{mate ? "Checkmate!" : "Stalemate"}</h2>
                    <button onClick={newGame}>New Game</button>
                </div>
            )}

            {check && !mate && !stalemate && (
                <div className="overlay"><h2>Check!</h2></div>
            )}

            {promo && (
                <PromotionModal
                    onSelect={(piece) => pushPlayerMove(promo.from, promo.to, piece)}
                    onCancel={() => setPromo(null)}
                />
            )}
        </>
    );
}
