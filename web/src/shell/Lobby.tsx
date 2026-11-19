import { useState, type FormEvent } from "react";
import "./lobby.css";
import { api } from "../api/client";
import { SEAT_PRESETS } from "./seatTypes";
import { errorText, type SeatType } from "./useGame";

interface Props {
  onCreated: (gameId: string) => void;
}

export default function Lobby({ onCreated }: Props) {
  const [players, setPlayers] = useState(2);
  const [seats, setSeats] = useState<SeatType[]>(["human", "random", "random", "random"]);
  const [joinery, setJoinery] = useState(true);
  const [returns, setReturns] = useState<"win_loss" | "margin">("win_loss");
  const [seed, setSeed] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const trimmed = seed.trim();
      const { data, error: err } = await api.POST("/api/games", {
        body: {
          game: "lignum",
          params: { num_players: players, joinery, returns },
          seats: seats.slice(0, players),
          ...(trimmed !== "" ? { seed: Number(trimmed) } : {}),
        },
      });
      if (data) onCreated(data.id);
      else setError(errorText(err));
    } catch (ex) {
      setError(ex instanceof Error ? ex.message : "Network error");
    } finally {
      setBusy(false);
    }
  }

  const seedBad = seed.trim() !== "" && !Number.isInteger(Number(seed.trim()));

  const humans = seats.slice(0, players).filter((s) => s === "human").length;

  return (
    <form className="panel-framed lobby-form" onSubmit={(e) => void submit(e)} aria-busy={busy}>
      <h2 className="lobby-title">
        <span className="num-tile">1</span> New game
      </h2>
      <div className="lobby-row">
        <div className="field">
          <label className="field-label" htmlFor="lobby-players">
            Players
          </label>
          <select
            id="lobby-players"
            value={players}
            onChange={(e) => setPlayers(Number(e.target.value))}
          >
            <option value={2}>2</option>
            <option value={3}>3</option>
            <option value={4}>4</option>
          </select>
        </div>
        <div className="field">
          <label className="field-label" htmlFor="lobby-returns">
            Returns
          </label>
          <select
            id="lobby-returns"
            value={returns}
            onChange={(e) => setReturns(e.target.value as "win_loss" | "margin")}
          >
            <option value="win_loss">Win / loss</option>
            <option value="margin">Margin</option>
          </select>
        </div>
      </div>
      <div className="lobby-toggle">
        <input
          id="lobby-joinery"
          type="checkbox"
          checked={joinery}
          aria-describedby="lobby-joinery-desc"
          onChange={(e) => setJoinery(e.target.checked)}
        />
        <div>
          <label htmlFor="lobby-joinery">Joinery and Buildings expansion</label>
          <p id="lobby-joinery-desc" className="lobby-hint">
            Adds joiners, craftwork and buildings to the year.
          </p>
        </div>
      </div>
      <fieldset className="lobby-seats">
        <legend className="field-label">Seats</legend>
        {seats.slice(0, players).map((s, i) => (
          <div key={i} className="lobby-seat" data-seat={i}>
            <span className="seat-tile" data-seat={i} aria-hidden="true">
              P{i}
            </span>
            <select
              aria-label={`Seat P${i}`}
              value={s}
              onChange={(e) =>
                setSeats(seats.map((x, j) => (j === i ? (e.target.value as SeatType) : x)))
              }
            >
              {SEAT_PRESETS.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </select>
          </div>
        ))}
        <p className="lobby-hint lobby-seats-hint">
          {humans > 1
            ? `Hotseat: ${humans} people share this screen.`
            : humans === 1
              ? "One person against bots."
              : "Bots only: the game plays itself to the end."}
        </p>
      </fieldset>
      <div className="field lobby-seed">
        <label className="field-label" htmlFor="lobby-seed">
          Seed (optional)
        </label>
        <input
          id="lobby-seed"
          value={seed}
          onChange={(e) => setSeed(e.target.value)}
          inputMode="numeric"
          placeholder="random"
          aria-invalid={seedBad || undefined}
        />
        <small>
          A fixed seed makes the bots and the card and token draws predictable; leave it empty
          for a random game.
        </small>
      </div>
      <div className="lobby-submit">
        <button type="submit" className="btn-primary btn-lg" disabled={busy || seedBad}>
          {busy ? (
            <>
              <span className="spinner" aria-hidden="true" /> Creating…
            </>
          ) : (
            "Create game"
          )}
        </button>
      </div>
      {error && (
        <p role="alert" className="alert">
          Error: {error}
        </p>
      )}
    </form>
  );
}
