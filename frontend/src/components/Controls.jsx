import React from "react";
import "./Controls.css";

/**
 * Top toolbar: new-game, side picker, music, volume, depth slider.
 *
 * Props
 * ─────
 * onNewGame()
 * playAsWhite            boolean
 * onSideChange(bool)     true = White
 * sideToMove             "White" | "Black"
 * musicPlaying           boolean
 * onToggleMusic()
 * volume, onVolumeChange
 * depth,  onDepthChange
 */
export default function Controls({
    onNewGame,
    playAsWhite,
    onSideChange,
    sideToMove,
    musicPlaying,
    onToggleMusic,
    volume,
    onVolumeChange,
    depth,
    onDepthChange,
}) {
    return (
        <div className="controls">
            <button onClick={onNewGame}>New&nbsp;Game</button>

            {/* side picker */}
            <label className="side-picker">
                Play as:&nbsp;
                <select
                    value={playAsWhite ? "white" : "black"}
                    onChange={(e) => onSideChange(e.target.value === "white")}
                >
                    <option value="white">White</option>
                    <option value="black">Black</option>
                </select>
            </label>

            <span className="turn">{sideToMove} to move</span>

            <button onClick={onToggleMusic}>
                {musicPlaying ? "Pause Music" : "Play Music"}
            </button>

            <label className="volume-slider">
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
