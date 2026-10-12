import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { api } from "../api/client";
import type { CaseDetail, RiskLevel } from "../api/types";
import { InlineError } from "./States";

const LEVELS: RiskLevel[] = ["low", "medium", "high", "critical"];

/** Opens a case (optionally linking alerts) and goes to it. */
export function NewCaseForm({ alertIds = [], defaultTitle = "", defaultPriority = "medium", onCancel }: {
  alertIds?: number[];
  defaultTitle?: string;
  defaultPriority?: RiskLevel;
  onCancel: () => void;
}) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [title, setTitle] = useState(defaultTitle);
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState<RiskLevel>(defaultPriority);
  const create = useMutation({
    mutationFn: () =>
      api<CaseDetail>("/cases", { method: "POST", body: { title, description, priority, alert_ids: alertIds } }),
    onSuccess: (created) => {
      queryClient.invalidateQueries();
      navigate(`/cases/${created.id}`);
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    create.mutate();
  }

  return (
    <form className="card form" onSubmit={submit} aria-label="New case">
      <h2>Open a case</h2>
      {alertIds.length > 0 && <p className="muted">Links {alertIds.length} alert(s): {alertIds.join(", ")}</p>}
      <label>
        Title
        <input required minLength={3} maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} />
      </label>
      <label>
        Description
        <textarea rows={3} maxLength={10000} value={description} onChange={(e) => setDescription(e.target.value)} />
      </label>
      <label>
        Priority
        <select value={priority} onChange={(e) => setPriority(e.target.value as RiskLevel)}>
          {LEVELS.map((l) => (
            <option key={l} value={l}>
              {l}
            </option>
          ))}
        </select>
      </label>
      <InlineError error={create.error} />
      <div className="actions">
        <button type="submit" className="btn btn-primary" disabled={create.isPending}>
          {create.isPending ? "Opening…" : "Open case"}
        </button>
        <button type="button" className="btn" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}
