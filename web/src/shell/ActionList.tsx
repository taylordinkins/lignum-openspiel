import Tip from "./Tip";
import type { LegalAction } from "./useGame";

interface Props {
  actions: LegalAction[];
  disabled: boolean;
  onAct: (id: number) => void;
  /** Optional display label; the action id is unchanged. */
  labelFor?: (a: LegalAction) => string;
  onHover?: (id: number | null) => void;
  /** Optional tooltip text for an action. */
  describe?: (a: LegalAction) => string | undefined;
}

/** Group actions by `kind` (first-appearance order); actions without a kind form one unnamed group. */
export function groupByKind(actions: LegalAction[]): { kind: string | null; actions: LegalAction[] }[] {
  const groups: { kind: string | null; actions: LegalAction[] }[] = [];
  for (const a of actions) {
    const kind = a.kind ?? null;
    let g = groups.find((x) => x.kind === kind);
    if (!g) {
      g = { kind, actions: [] };
      groups.push(g);
    }
    g.actions.push(a);
  }
  return groups;
}

/** Every legal action as a labelled button, grouped by kind when the server provides one. */
export default function ActionList({ actions, disabled, onAct, labelFor, onHover, describe }: Props) {
  if (actions.length === 0) return <p>No actions available.</p>;
  return (
    <div>
      {groupByKind(actions).map((g) => (
        <section key={g.kind ?? "_"} aria-label={g.kind ? `Kind ${g.kind}` : undefined}>
          {g.kind && <h3 className="lg-kind">{g.kind.replace(/_/g, " ")}</h3>}
          <ul aria-label={g.kind ? `Legal actions: ${g.kind}` : "Legal actions"} className="lg-actions">
            {g.actions.map((a) => (
              <li key={a.id}>
                <Tip text={describe?.(a)}>
                  <button
                    type="button"
                    disabled={disabled}
                    onClick={() => onAct(a.id)}
                    onMouseEnter={() => onHover?.(a.id)}
                    onMouseLeave={() => onHover?.(null)}
                    onFocus={() => onHover?.(a.id)}
                    onBlur={() => onHover?.(null)}
                  >
                    {labelFor ? labelFor(a) : a.label}
                  </button>
                </Tip>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
