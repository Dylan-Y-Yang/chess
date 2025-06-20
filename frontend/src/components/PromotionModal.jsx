// frontend/src/components/PromotionModal.jsx
import React, { useState } from "react";
import "./PromotionModal.css";

const OPTIONS = [
    { label: "Queen", value: "Q" },
    { label: "Rook", value: "R" },
    { label: "Bishop", value: "B" },
    { label: "Knight", value: "N" },
];

export default function PromotionModal({ onPromote, onCancel }) {
    const [choice, setChoice] = useState("Q");

    return (
        <div className="promo-overlay" onClick={onCancel}>
            <div className="promo-modal" onClick={e => e.stopPropagation()}>
                <h2>Promotion</h2>
                <select
                    value={choice}
                    onChange={e => setChoice(e.target.value)}
                >
                    {OPTIONS.map(o => (
                        <option key={o.value} value={o.value}>
                            {o.label}
                        </option>
                    ))}
                </select>
                <div className="promo-buttons">
                    <button onClick={() => onPromote(choice)}>Promote</button>
                    <button onClick={onCancel}>Cancel</button>
                </div>
            </div>
        </div>
    );
}
