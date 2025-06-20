import React from "react";
import "./Board.css";

/* -------- helpers -------- */
const files = "abcdefgh";
const ranks = "12345678";
const rcToSq = (r, c) => files[c] + ranks[7 - r];

const glyph = {
    P: "♙", N: "♘", B: "♗", R: "♖", Q: "♕", K: "♔",
    p: "♟︎", n: "♞", b: "♝", r: "♜", q: "♛", k: "♚",
    ".": "",
};

/**
 * Board grid.
 * Props
 *   board        – 8×8 array of FEN letters
 *   selected     – square like "e2" or null
 *   legalMoves   – array of squares ["e4", …]
 *   onSquareClick(sq)
 *   flip         – boolean (true = show from Black's POV)
 */
export default function Board({
    board,
    selected,
    legalMoves,
    onSquareClick,
    flip = false,
}) {
    if (!board?.length) return null;   // still loading

    return (
        <div className="board-wrapper">
            <div className="board">
                {/* display rows 0..7 but map to real indices depending on flip */}
                {Array.from({ length: 8 }, (_, rDisp) =>
                    Array.from({ length: 8 }, (_, cDisp) => {
                        const rReal = flip ? 7 - rDisp : rDisp;
                        const cReal = flip ? 7 - cDisp : cDisp;
                        const sq = rcToSq(rReal, cReal);

                        const piece = board[rReal][cReal];
                        const light = (rDisp + cDisp) % 2 === 0;
                        const isSel = selected === sq;
                        const isLegal = legalMoves?.includes(sq);

                        return (
                            <div
                                key={sq}
                                className={[
                                    "square",
                                    light ? "light" : "dark",
                                    isSel && "selected",
                                    isLegal && "legal",
                                ]
                                    .filter(Boolean)
                                    .join(" ")}
                                onClick={() => onSquareClick(sq)}
                            >
                                <span className="piece">{glyph[piece] || ""}</span>
                            </div>
                        );
                    })
                )}
            </div>
        </div>
    );
}
