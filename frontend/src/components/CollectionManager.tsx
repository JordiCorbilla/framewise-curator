import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Pencil, Trash2 } from "lucide-react";
import { api } from "../services/api";
import { Modal } from "./Modal";
import { Button } from "./ui/button";
import { active } from "./Progress";
import type { Library } from "../types";

export function CollectionManager({
  library,
  refresh,
  removed,
}: {
  library: Library;
  refresh: () => void;
  removed: () => void;
}) {
  const [mode, setMode] = useState<"rename" | "remove" | null>(null);
  const [title, setTitle] = useState(library.name);
  const [confirmation, setConfirmation] = useState("");
  const update = useMutation({
    mutationFn: () =>
      mode === "rename"
        ? api(`/libraries/${library.id}`, "PATCH", { name: title.trim() })
        : api(`/libraries/${library.id}`, "DELETE", {
            confirm_name: confirmation,
          }),
    onSuccess: () => {
      if (mode === "remove") removed();
      refresh();
      setMode(null);
    },
  });
  return (
    <>
      <div className="collection-management">
        <button
          aria-label={`Rename ${library.name}`}
          onClick={() => {
            setTitle(library.name);
            update.reset();
            setMode("rename");
          }}
        >
          <Pencil size={13} />
          Rename
        </button>
        <button
          aria-label={`Remove ${library.name}`}
          disabled={active(library.job)}
          title={
            active(library.job)
              ? "Wait until the scan stops"
              : "Remove app records and cached previews"
          }
          onClick={() => {
            setConfirmation("");
            update.reset();
            setMode("remove");
          }}
        >
          <Trash2 size={13} />
          Remove
        </button>
      </div>
      {mode && (
        <Modal
          title={
            mode === "rename"
              ? "Rename collection"
              : "Remove collection permanently"
          }
          close={() => {
            if (!update.isPending) setMode(null);
          }}
        >
          <form
            className="collection-form"
            onSubmit={(e) => {
              e.preventDefault();
              update.mutate();
            }}
          >
            {mode === "rename" ? (
              <label>
                Collection title
                <input
                  autoComplete="off"
                  maxLength={200}
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                />
              </label>
            ) : (
              <>
                <p>
                  This removes <strong>{library.name}</strong>, its selections,
                  ratings, taste labels and cached previews from Framewise. This
                  cannot be undone.
                </p>
                <p>
                  Your original photographs and source folder stay untouched.
                  Your local taste model will be reset because it may have
                  learned from this collection. Other collections’ feedback
                  stays available for retraining.
                </p>
                <label>
                  Type <strong>{library.name}</strong> to confirm
                  <input
                    autoComplete="off"
                    value={confirmation}
                    onChange={(e) => setConfirmation(e.target.value)}
                  />
                </label>
              </>
            )}
            {update.error && (
              <p className="error" role="alert">
                {update.error.message}
              </p>
            )}
            <div className="form-actions">
              <Button
                variant="outline"
                type="button"
                disabled={update.isPending}
                onClick={() => setMode(null)}
              >
                Cancel
              </Button>
              <Button
                className={mode === "remove" ? "danger-button" : ""}
                disabled={
                  update.isPending ||
                  (mode === "rename"
                    ? !title.trim()
                    : confirmation !== library.name)
                }
              >
                {update.isPending
                  ? "Saving…"
                  : mode === "rename"
                    ? "Save title"
                    : "Remove permanently"}
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </>
  );
}
