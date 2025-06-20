import React from "react";
import "./PromotionModal.css";

/**
 * Modal asking which piece to promote to.
 *
 * Props
 * ─────
 * onSelect(piece)   piece ∈ {"Q","R","B","N"}
 * onCancel()
 */
export default function PromotionModal({ onSelect, onCancel }) {
    const pieces = ["Q", "R", "B", "N"];
    const glyph = { Q: "♕", R: "♖", B: "♗", N: "♘" };

    return (
        <div className="promo-overlay" onClick={onCancel}>
            <div className="promo-dialog" onClick={(e) => e.stopPropagation()}>
                <h3>Choose promotion piece</h3>
                <div className="promo-grid">
                    {pieces.map((p) => (
                        <button
                            key={p}
                            className="promo-btn"
                            onClick={() => onSelect(p)}
                            title={p}
                        >
                            {glyph[p]}
                        </button>
                    ))}
                </div>

                <button className="cancel-btn" onClick={onCancel}>
                    Cancel
                </button>
            </div>
        </div>
    );
}
