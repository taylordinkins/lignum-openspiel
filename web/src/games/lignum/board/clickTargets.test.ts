import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { LegalAction } from "../../../shell/useGame";
import { LIST_ONLY, ON_BOARD_KINDS, targetsFor, unmapped } from "./clickTargets";

const la = (id: number, kind: string, params: number[], label = `${kind}${params}`): LegalAction => ({ id, kind, params, label });

const root = resolve(__dirname, "../../../../..");
/** Every action family the adapter can label (keys of _ACTION_FMT). */
function adapterKinds(): string[] {
  const src = readFileSync(resolve(root, "server/adapters/lignum.py"), "utf8");
  const body = src.slice(src.indexOf("_ACTION_FMT"));
  return [...body.slice(0, body.indexOf("\n}")).matchAll(/^ {4}"([A-Z_]+)":/gm)].map((m) => m[1]!);
}

describe("targetsFor", () => {
  it("maps PICK_AREA and MOVE_CUT_TOKEN to cutting areas (1-based)", () => {
    const t = targetsFor([la(2, "PICK_AREA", [0]), la(7, "PICK_AREA", [5]), la(170, "MOVE_CUT_TOKEN", [2])]);
    expect(t.map((x) => [x.region, x.actions.map((a) => a.id)])).toEqual([
      [{ type: "area", n: 1 }, [2]],
      [{ type: "area", n: 6 }, [7]],
      [{ type: "area", n: 3 }, [170]],
    ]);
  });

  it("groups several actions in one area (TAKE_WOOD kinds, HUT_FOOD)", () => {
    const t = targetsFor([la(177 + 3, "TAKE_WOOD", [1, 0]), la(177 + 4, "TAKE_WOOD", [1, 1]), la(145, "HUT_FOOD", [1])]);
    expect(t).toHaveLength(1);
    expect(t[0]!.region).toEqual({ type: "area", n: 2 });
    expect(t[0]!.actions.map((a) => a.id)).toEqual([180, 181, 145]);
  });

  it("maps MOVE_TO to path locations and 23 to the clearing", () => {
    const t = targetsFor([la(8, "MOVE_TO", [1]), la(30, "MOVE_TO", [23])]);
    expect(t.map((x) => x.region)).toEqual([{ type: "location", n: 1 }, { type: "clearing" }]);
  });

  it("ignores actions without kind/params and list-only kinds", () => {
    const legal: LegalAction[] = [{ id: 0, label: "Done" }, la(0, "DONE", []), la(1, "TAKE_LOAN", []), la(2, "PICK_AREA", [9])];
    expect(targetsFor(legal)).toEqual([]);
    expect(unmapped(legal)).toHaveLength(4);
  });
});

describe("coverage", () => {
  it("every adapter action family is either on the board or in LIST_ONLY, never both", () => {
    const kinds = adapterKinds();
    expect(kinds.length).toBeGreaterThan(30);
    for (const k of kinds) expect(ON_BOARD_KINDS.has(k) !== LIST_ONLY.has(k), k).toBe(true);
    for (const k of [...ON_BOARD_KINDS, ...LIST_ONLY]) expect(kinds, k).toContain(k);
  });

  it("unmapped() returns exactly the actions the list must still offer", () => {
    const legal = [la(0, "DONE", []), la(2, "PICK_AREA", [0]), la(31, "HIRE_BEARER", []), la(8, "MOVE_TO", [3])];
    expect(unmapped(legal).map((a) => a.id)).toEqual([0, 31]);
  });
});
