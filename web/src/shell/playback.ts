import { useCallback, useEffect, useRef, useState } from "react";
import type { components } from "../api/schema";
import type { GameView } from "./useGame";

export type HistoryEntry = components["schemas"]["HistoryEntry"];

/**
 * Client-side playback of new history entries (UI_DESIGN §7, §6.8).
 *
 * The server plays bot turns at once; the client shows them one at a time, `pace` seconds apart,
 * by fetching read-only frames (`GET /api/games/{id}?at=N`). Human (and chance) entries are shown
 * immediately.
 */

/** A playback step ends after history entry `end - 1`; `bot` steps wait for the pace. */
export interface Step {
  end: number;
  bot: boolean;
}

const isBotEntry = (g: GameView, e: HistoryEntry): boolean =>
  e.actor !== null && e.actor !== undefined && g.seats[e.actor] !== "human";

/**
 * Split `target.history[from:]` into steps: each bot entry is its own step; runs of human entries
 * are merged into one; chance entries (actor null) join the step before them.
 */
export function planSteps(target: GameView, from: number): Step[] {
  const steps: Step[] = [];
  const entries = target.history;
  for (let i = from; i < entries.length; i++) {
    const e = entries[i]!;
    const last = steps[steps.length - 1];
    const bot = isBotEntry(target, e);
    if (last && (e.actor === null || e.actor === undefined || (!bot && !last.bot))) last.end = i + 1;
    else steps.push({ end: i + 1, bot });
  }
  return steps;
}

/** True when `next` is the same game as `prev` with `prev`'s history as a prefix (no Back). */
export function extendsView(prev: GameView, next: GameView): boolean {
  if (prev.id !== next.id || next.history_length < prev.history_length) return false;
  const k = prev.history_length - 1;
  if (k < 0) return true;
  const a = prev.history[k];
  const b = next.history[k];
  if (!a || !b) return prev.history.length === 0;
  if (a.actor !== b.actor) return false;
  // another seat's pick is masked (id null) until all picks are in, then revealed: same entry
  if (a.id === null || a.id === undefined || b.id === null || b.id === undefined) return true;
  return a.id === b.id && a.label === b.label;
}

/** A human seat is to move, or the game is over: where "Skip to my turn" stops. */
export const atHumanTurnOrEnd = (g: GameView): boolean =>
  g.is_terminal || (g.current_player !== null && g.seats[g.current_player] === "human");

export interface PlaybackOptions {
  /** Seconds between paced bot moves; 0 shows the latest state at once. */
  pace: number;
  /** Fetch the read-only frame after the first `at` entries; null on failure. */
  fetchFrame: (at: number, seat: number) => Promise<GameView | null>;
}

export interface Playback {
  /** The view to render (lags `latest` while bot moves are played back). */
  shown: GameView | null;
  /** True while `shown` is behind `latest`: no input is accepted. */
  behind: boolean;
  /** Fast-forward to the next human turn (or the end). */
  skip: () => void;
  skipping: boolean;
}

export function usePlayback(latest: GameView | null, { pace, fetchFrame }: PlaybackOptions): Playback {
  const [shown, setShown] = useState<GameView | null>(latest);
  const [skipping, setSkipping] = useState(false);
  const shownRef = useRef<GameView | null>(latest);
  const target = useRef<GameView | null>(latest);
  const paceRef = useRef(pace);
  paceRef.current = pace;
  const fetchRef = useRef(fetchFrame);
  fetchRef.current = fetchFrame;
  const skipRef = useRef(false);
  const gen = useRef(0);
  const running = useRef(false);
  const lastChange = useRef(Date.now());
  const wake = useRef<(() => void) | null>(null);
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      gen.current += 1;
      wake.current?.();
    };
  }, []);

  const show = useCallback((v: GameView) => {
    if (shownRef.current?.history_length !== v.history_length) lastChange.current = Date.now();
    shownRef.current = v;
    setShown(v);
    if (skipRef.current && atHumanTurnOrEnd(v)) {
      skipRef.current = false;
      setSkipping(false);
    }
  }, []);

  const sleep = (ms: number) =>
    new Promise<void>((resolve) => {
      const t = setTimeout(done, ms);
      function done() {
        clearTimeout(t);
        wake.current = null;
        resolve();
      }
      wake.current = done;
    });

  const run = useCallback(async () => {
    if (running.current) return;
    running.current = true;
    const g = gen.current;
    try {
      while (alive.current && gen.current === g) {
        const tg = target.current;
        const cur = shownRef.current;
        if (!tg || !cur || !extendsView(cur, tg) || tg.history_length <= cur.history_length) break;
        if (skipRef.current) {
          show(tg);
          continue;
        }
        if (paceRef.current <= 0) {
          show(tg);
          continue;
        }
        const step = planSteps(tg, cur.history_length)[0];
        if (!step) break;
        if (step.bot) {
          const wait = lastChange.current + paceRef.current * 1000 - Date.now();
          if (wait > 0) await sleep(wait);
          if (gen.current !== g || !alive.current) break;
          if (skipRef.current) continue;
        }
        const tg2 = target.current;
        if (!tg2 || !extendsView(cur, tg2) || shownRef.current !== cur) continue;
        let frame: GameView | null = step.end === tg2.history_length ? tg2 : null;
        if (frame === null) {
          try {
            frame = await fetchRef.current(step.end, tg2.seat);
          } catch {
            frame = null;
          }
          if (gen.current !== g || !alive.current) break;
        }
        if (!frame || frame.history_length !== step.end || !extendsView(cur, frame)) {
          // frame unavailable (history changed meanwhile): jump to the latest state
          const now = target.current;
          if (now) show(now);
          continue;
        }
        show(frame);
      }
    } finally {
      running.current = false;
      const tg = target.current;
      const cur = shownRef.current;
      if (alive.current && gen.current !== g && tg && cur && extendsView(cur, tg) && tg.history_length > cur.history_length) {
        void run(); // Back bumped gen while this loop was in flight: pick up what arrived since
      }
    }
  }, [show]);

  useEffect(() => {
    target.current = latest;
    if (latest === null) return;
    const cur = shownRef.current;
    if (cur === null || !extendsView(cur, latest)) {
      // first load, another game, Back or rewind: show at once, no motion
      gen.current += 1;
      wake.current?.();
      show(latest);
      return;
    }
    if (latest.history_length === cur.history_length) {
      if (!running.current) show(latest); // same position (poll, seat change)
      return;
    }
    void run();
  }, [latest, run, show]);

  const skip = useCallback(() => {
    const tg = target.current;
    if (tg && atHumanTurnOrEnd(tg) && shownRef.current === tg) return;
    skipRef.current = true;
    setSkipping(true);
    wake.current?.();
    const cur = shownRef.current;
    if (tg && cur && tg !== cur && !running.current) show(tg);
  }, [show]);

  const behind = latest !== null && shown !== null && shown !== latest && shown.history_length !== latest.history_length;
  return { shown, behind, skip, skipping };
}
