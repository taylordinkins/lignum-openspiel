import { useState, type ChangeEvent } from "react";
import { api } from "../api/client";
import { IconUpload } from "../theme/icons";
import { errorText } from "./useGame";

interface Props {
  onImported: (gameId: string) => void;
  /** "icon" is the compact toolbar form (tooltip, same accessible name). */
  variant?: "labelled" | "icon";
}

/** File input that posts a replay export to /api/games/import. */
export default function ImportButton({ onImported, variant = "labelled" }: Props) {
  const [error, setError] = useState<string | null>(null);

  async function pick(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    try {
      const body = JSON.parse(await file.text());
      const { data, error: err } = await api.POST("/api/games/import", {
        body,
      });
      if (data) onImported(data.id);
      else setError(errorText(err));
    } catch (ex) {
      setError(ex instanceof Error ? ex.message : "Import failed");
    }
  }

  const icon = variant === "icon";
  const control = (
    <label className={icon ? "btn btn-sm btn-icon btn-ghost import-btn" : "btn import-btn"}>
      <IconUpload />
      <span className={icon ? "sr-only" : undefined}>Import replay</span>
      <input className="sr-only" type="file" accept="application/json,.json" onChange={(e) => void pick(e)} />
    </label>
  );
  return (
    <span className="import">
      {icon ? (
        <span className="tip" data-tip="Import replay">
          {control}
        </span>
      ) : (
        control
      )}
      {error && (
        <p role="alert" className={icon ? "alert toast" : "alert"}>
          Import error: {error}
        </p>
      )}
    </span>
  );
}
