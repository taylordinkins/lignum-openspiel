import { useState, type FormEvent } from "react";
import { api } from "../api/client";
import { errorText } from "./useGame";
import { useDialog } from "./useDialog";

interface Props {
  gameId: string;
  onClose: () => void;
}

const CATEGORIES = ["engine", "ui", "other"] as const;

export default function ReportDialog({ gameId, onClose }: Props) {
  const [note, setNote] = useState("");
  const [category, setCategory] = useState<string>("other");
  const [error, setError] = useState<string | null>(null);
  const [reportId, setReportId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const ref = useDialog(onClose);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (note.trim() === "") {
      setError("Note is required");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const { data, error: err } = await api.POST("/api/games/{game_id}/report", {
        params: { path: { game_id: gameId } },
        body: { note, category },
      });
      if (data) setReportId(data.report_id);
      else setError(errorText(err));
    } catch (ex) {
      setError(ex instanceof Error ? ex.message : "Network error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="dlg-backdrop">
      <div ref={ref} role="dialog" aria-modal="true" aria-label="Report a problem" className="dlg lg-report">
        <form onSubmit={(e) => void submit(e)}>
          <p className="eyebrow">Playtest feedback</p>
          <h2>Report a problem</h2>
          <p className="lg-report-lead">
            The report saves this game&rsquo;s full history with your note, so the exact position can be
            replayed.
          </p>
          <label className="field">
            <span className="field-label">Category</span>{" "}
            <select value={category} onChange={(e) => setCategory(e.target.value)}>
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </label>
          <div>
            <label className="field">
              <span className="field-label">Note</span>{" "}
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                rows={5}
                placeholder="What happened, and what did you expect?"
              />
            </label>
          </div>
          {reportId && (
            <p role="status" className="note lg-report-ok">
              Report sent. Report id: {reportId}
            </p>
          )}
          {error && (
            <p role="alert" className="alert">
              Error: {error}
            </p>
          )}
          <div className="dlg-actions">
            <button type="button" className="btn" onClick={onClose}>
              Close report
            </button>
            <button type="submit" className="btn btn-primary" disabled={busy || reportId !== null}>
              Submit report
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
