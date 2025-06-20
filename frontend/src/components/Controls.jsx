import React from "react";
import "./Controls.css";

/**
 * Top-bar buttons + sliders
 *
 * Props
 * ─────
 * onNewGame()               – reset board
 * sideToMove                – "White" | "Black"
 * musicPlaying              – boolean
 * onToggleMusic()           – play / pause bgm
 * volume                    – 0‒1
 * onVolumeChange(v:number)
 * depth                     – integer (1‒8)
 * onDepthChange(d:number)
 */
export default function Controls({
    onNewGame,
    sideToMove,
    musicPlaying,
    onToggleMusic,
    volume,
    onVolumeChange,
    depth,
    onDepthChange
}) {
    return (
        <div className="controls">
            <button onClick={onNewGame}>New&nbsp;Game</button>
            <span className="side-label">{sideToMove} to move</span>

            <button onClick={onToggleMusic}>
                {musicPlaying ? "Pause Music" : "Play Music"}
            </button>

            <label className="volume">
                Volume&nbsp;
                <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.02"
                    value={volume}
                    onChange={(e) => onVolumeChange(+e.target.value)}
                />
            </label>

            {/* NEW — depth slider */}
            <label className="depth">
                Depth:&nbsp;<span>{depth}</span>
                <input
                    type="range"
                    min="1"
                    max="8"
                    step="1"
                    value={depth}
                    onChange={(e) => onDepthChange(+e.target.value)}
                />
            </label>
        </div>
    );
}
