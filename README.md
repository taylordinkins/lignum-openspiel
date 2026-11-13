# Lignum

An unofficial, non-commercial digital version of *Lignum* (2nd edition) with the
*Joinery and Buildings* expansion, playable in your browser against bots or hotseat with friends.

*Lignum* was designed by **Alexander Huemer** and is published by **Capstone Games**. All rights
to the game, its name, rules and artwork belong to them. This project is not affiliated with or
endorsed by the designer or publisher. If you enjoy it, please buy the physical game.

## What you need

- [Git](https://git-scm.com/downloads)
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (installs the right Python for you)
- [Node.js](https://nodejs.org/) 18.18 or newer

## Setup (once)

```bash
git clone https://github.com/taylordinkins/lignum-openspiel.git
cd lignum-openspiel
uv sync
cd web && npm ci && cd ..
```

## Play

**macOS / Linux / WSL**: one command starts everything:

```bash
tools/dev.sh
```

**Windows (PowerShell)**: open two terminals in the `lignum-openspiel` folder:

```powershell
# Terminal 1: game server
uv run uvicorn server.app:app --port 8000
```

```powershell
# Terminal 2: web page
cd web
npm run dev
```

Then open **http://localhost:5173** in your browser.

## Starting a game

On the **New game** screen:

1. Pick the number of **Players** (2–4).
2. For each seat (`P0`, `P1`, …) choose **Human** or a bot. **Strategist bot** or **AZ bot** are
   the strongest opponents; **Heuristic bot** is a lighter one.
3. Leave **Joinery and Buildings expansion** ticked to play with the expansion.
4. Click **Create game**.

With several human seats, the game hands off between them on the same screen.

## Theme

The game uses the **generic** theme: original artwork made for this project, and the one we
suggest. The official *Lignum* art is not included in this repository.

If you own a local copy of the official art in `third_party/art/`, you can enable it by starting
the web page with `VITE_LIGNUM_OFFICIAL_THEME=1` set (for example `VITE_LIGNUM_OFFICIAL_THEME=1 tools/dev.sh`,
or `$env:VITE_LIGNUM_OFFICIAL_THEME=1` in PowerShell before `npm run dev`). A **Theme** dropdown then
appears at the top of the board to switch between `generic` and `official`; your choice is
remembered in this browser.
