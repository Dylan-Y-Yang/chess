import React, { useState, useEffect } from "react";
import axios from "axios";
import Board from "./components/Board";
import Controls from "./components/Controls";
import PromotionModal from "./components/PromotionModal";

/* ---- audio ---- */
const bg = (() => { const a = new Audio("/static/background.mp3"); a.loop = true; a.volume = 0.2; return a; })();
const sfxSel = new Audio("/static/select.mp3");
const sfxMove = new Audio("/static/move.mp3");
const sfxChk = new Audio("/static/check.mp3");
const sfxMate = new Audio("/static/checkmate.mp3");

/* ---- helpers ---- */
const f2c = f => f.charCodeAt(0) - 97, r2row = r => 8 - +r;
const sq2rc = sq => [r2row(sq[1]), f2c(sq[0])];

export default function App() {
    const [board, setBoard] = useState([]);
    const [white, setWhite] = useState(true);
    const [sel, setSel] = useState(null);
    const [legal, setLegal] = useState([]);
    const [check, setCheck] = useState(false);
    const [mate, setMate] = useState(false);
    const [promo, setPromo] = useState(null);
    const [play, setPlay] = useState(false);
    const [vol, setVol] = useState(0.2);

    useEffect(() => { newGame(); }, []);
    useEffect(() => { bg.volume = vol; play ? bg.play().catch(() => { }) : bg.pause(); }, [play, vol]);

    async function newGame() {
        const r = await axios.post("/newgame");
        setBoard(r.data.board); setWhite(r.data.white_to_move);
        setSel(null); setLegal([]); setCheck(false); setMate(false); setPromo(null);
    }

    /* ---------- click handling ---------- */
    async function onSquareClick(sq) {
        if (promo) return;               // ignore during promotion
        const [r, c] = sq2rc(sq); const piece = board[r][c];

        // first click: select
        if (!sel) {
            if (piece === ".") return;
            sfxSel.play();
            setSel(sq);
            try {
                const lm = await axios.get("/legal_moves", { params: { from_square: sq } });
                setLegal(lm.data.moves);
            } catch { setLegal([]); }
            return;
        }

        // second click: must match a legal target
        const mv = legal.find(m => m.to === sq);
        if (!mv) {
            setSel(null); setLegal([]); return;
        }
        if (mv.promotion) {
            setPromo({ from: sel, to: sq }); return;
        }
        await playHumanMove(sel, sq, null);
    }

    async function playHumanMove(from, to, prom) {
        /* 1) apply human move */
        let res;
        try {
            res = await axios.post("/move", { from_square: from, to_square: to, promotion: prom });
        } catch (err) { console.error(err.response?.data || err); return; }

        sfxMove.play();
        updateFromServer(res);

        /* 2) if bot needed, request it */
        if (res.data.bot_needed) {
            try {
                const bot = await axios.post("/bot_move");
                sfxMove.play();
                updateFromServer(bot);
            } catch (err) { console.error(err.response?.data || err); }
        }
    }

    function updateFromServer(data) {
        setBoard(data.data.board);
        setWhite(data.data.white_to_move);
        if (data.data.checkmate) { setMate(true); sfxMate.play(); }
        else if (data.data.check) { setCheck(true); sfxChk.play(); }
        else { setCheck(false); setMate(false); }
        setSel(null); setLegal([]); setPromo(null);
    }

    return (
        <div className="app">
            <h1>Chess Bot</h1>
            <Controls onNewGame={newGame} whiteToMove={white}
                isPlaying={play} togglePlay={() => setPlay(p => !p)}
                volume={vol} setVolume={setVol} />
            <div className="board-wrapper">
                <Board board={board} selected={sel} legalMoves={legal.map(m => m.to)}
                    onSquareClick={onSquareClick} />
            </div>
            {mate && <div className="popup-overlay"><div className="popup"><h2>Checkmate!</h2><button onClick={newGame}>New Game</button></div></div>}
            {check && !mate && <div className="alert alert--check">Check!</div>}
            {promo && <PromotionModal onPromote={piece => playHumanMove(promo.from, promo.to, piece)} onCancel={() => setPromo(null)} />}
        </div>);
}
