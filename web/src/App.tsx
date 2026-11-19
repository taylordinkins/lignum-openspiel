import { useEffect, useState } from "react";
import GameScreen from "./shell/GameScreen";
import ImportButton from "./shell/ImportButton";
import Lobby from "./shell/Lobby";
import { Wordmark } from "./theme/Wordmark";
import boardUrl from "../../assets/generic/boards/board.svg?url";
import "./shell/lobby.css";

const parseHash = (): string | null => {
  const m = /^#\/game\/(.+)$/.exec(window.location.hash);
  return m?.[1] ? decodeURIComponent(m[1]) : null;
};

const goTo = (id: string) => {
  window.location.hash = `#/game/${encodeURIComponent(id)}`;
};

export default function App() {
  const [gameId, setGameId] = useState<string | null>(parseHash);

  useEffect(() => {
    const onHash = () => setGameId(parseHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  if (gameId) {
    return (
      <main className="app-game">
        <GameScreen
          key={gameId}
          gameId={gameId}
          onExit={() => {
            window.location.hash = "";
          }}
          onImported={goTo}
        />
      </main>
    );
  }

  return (
    <main className="app-lobby">
      <header className="lobby-hero">
        <h1 className="lobby-wordmark">
          <Wordmark size="lg" />
        </h1>
        <div className="lobby-hero-text">
          <p className="eyebrow">Lignum · second edition · Joinery and Buildings expansion</p>
          <p className="lobby-tagline">Fell, saw, dry and sell before the second winter.</p>
          <p className="lobby-sub">2 to 4 seats, any mix of people at this screen and bots.</p>
        </div>
      </header>
      <div className="lobby-grid">
        <Lobby onCreated={goTo} />
        <aside className="lobby-aside">
          <figure className="lobby-board" aria-hidden="true">
            <img src={boardUrl} alt="" decoding="async" />
          </figure>
          <section className="card lobby-card" aria-label="Load a replay">
            <h2 className="lobby-title">
              <span className="num-tile">2</span> Continue a game
            </h2>
            <p className="lobby-hint">
              Load a replay exported from an earlier game; play resumes where it stopped.
            </p>
            <ImportButton onImported={goTo} />
          </section>
          <section className="card lobby-card lobby-tips" aria-label="How to play here">
            <h2 className="lobby-title">
              <span className="num-tile">3</span> At the table
            </h2>
            <ul>
              <li>
                <b>Click what glows,</b> or use the action chips under the board.
              </li>
              <li>
                <b>Hidden picks</b> are covered by a hand-off curtain when people share a screen.
              </li>
              <li>
                <b>Back</b> undoes your last decision.
              </li>
            </ul>
          </section>
        </aside>
      </div>
    </main>
  );
}
