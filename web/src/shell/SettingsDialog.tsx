import { useDialog } from "./useDialog";
import { BOT_PACE_MAX, useSettings } from "./settings";

/** Bot pacing; saved in this browser. */
export default function SettingsDialog({ onClose }: { onClose: () => void }) {
  const [s, update] = useSettings();
  const ref = useDialog(onClose);
  return (
    <div className="dlg-backdrop" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div ref={ref} role="dialog" aria-modal="true" aria-label="Settings" className="dlg lg-settings">
        <p className="eyebrow">This browser</p>
        <h2>Settings</h2>
        <label className="field lg-settings-group">
          <span className="field-label">
            Bot pace <output className="lg-settings-value">{s.botPace.toFixed(1)} s</output>
          </span>
          <input
            type="range"
            aria-label="Bot pace (seconds per move)"
            min={0}
            max={BOT_PACE_MAX}
            step={0.1}
            value={s.botPace}
            onChange={(e) => update({ botPace: Number(e.target.value) })}
          />
          <span className="lg-settings-hint">Pause between bot moves; 0 shows them all at once.</span>
        </label>
        <div className="dlg-actions">
          <button type="button" className="btn btn-primary" onClick={onClose}>
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
