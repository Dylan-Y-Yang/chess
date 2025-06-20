// Board.jsx
import React from "react";
import "./Board.css";

const UNI = {
    P: "♙", R: "♖", N: "♘", B: "♗", Q: "♕", K: "♔",
    p: "♟", r: "♜", n: "♞", b: "♝", q: "♛", k: "♚",
    ".": ""
};

export default function Board({ board, selected, legalMoves, onSquareClick }) {
    return (
        <div className="board">
            {board.map((row, r) =>
                row.map((piece, c) => {
                    const file = String.fromCharCode(97 + c); // a-h
                    const rank = 8 - r;                       // 8-1
                    const sq = `${file}${rank}`;

                    const isLight = (r + c) % 2 === 0;
                    const isSelected = selected === sq;
                    const isLegal = legalMoves.includes(sq);

                    return (
                        <div
                            key={sq}
                            className={
                                `square ${isLight ? "light" : "dark"} ` +
                                (isSelected ? "selected " : "") +
                                (isLegal ? "legal" : "")
                            }
                            onClick={() => onSquareClick(sq)}
                        >
                            <span className="piece">{UNI[piece]}</span>
                        </div>
                    );
                })
            )}
        </div>
    );
}
