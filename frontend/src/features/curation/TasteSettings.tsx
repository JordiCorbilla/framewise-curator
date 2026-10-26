import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Brain, ThumbsUp, ThumbsDown } from "lucide-react";
import { useState } from "react";
import { api } from "../../services/api";
import { Button } from "../../components/ui/button";
import { Modal } from "../../components/Modal";

interface Taste {
  status: string;
  enabled: boolean;
  labels: number;
  usable_likes: number;
  usable_dislikes: number;
  conflicting_groups: number;
  minimum_per_class: number;
  reason: string;
  training_count?: number;
  heldout_count?: number;
  heldout_balanced_accuracy?: number;
  eligible?: boolean;
  version?: string;
}

export function TasteSettings() {
  const client = useQueryClient();
  const [forget, setForget] = useState(false);
  const result = useQuery({
    queryKey: ["taste"],
    queryFn: () => api<Taste>("/taste"),
  });
  const action = useMutation({
    mutationFn: (operation: "train" | "enable" | "disable" | "forget") =>
      operation === "train"
        ? api("/taste/train", "POST", {})
        : operation === "forget"
          ? api("/taste", "DELETE", {})
          : api("/taste", "PATCH", { enabled: operation === "enable" }),
    onSuccess: () => {
      setForget(false);
      for (const key of [
        "taste",
        "taste-label",
        "photos",
        "photo",
        "highlights",
        "libraries",
      ])
        void client.invalidateQueries({ queryKey: [key] });
    },
  });
  const taste = result.data;
  return (
    <section className="settings-section taste-settings">
      <div className="settings-title">
        <Brain size={20} />
        <h2>Your taste, learned locally</h2>
        <span className={`model-pill ${taste?.enabled ? "sage" : ""}`}>
          {taste?.enabled
            ? "Applied · 30% blend"
            : taste?.status === "trained"
              ? "Trained · paused"
              : "Collecting feedback"}
        </span>
      </div>
      <p>
        Open a photo and choose <strong>My taste → Like or Dislike</strong>.
        Give both good and bad examples across your collections. Keep/Exclude
        and stars remain editing decisions; they never become training labels
        automatically.
      </p>
      {taste && (
        <>
          <div className="taste-counts">
            <span>
              <ThumbsUp size={16} />
              <b>{taste.usable_likes}</b> distinct likes
            </span>
            <span>
              <ThumbsDown size={16} />
              <b>{taste.usable_dislikes}</b> distinct dislikes
            </span>
          </div>
          <p className="footnote">
            {taste.labels} labels saved. At least {taste.minimum_per_class}{" "}
            distinct frames per class with cached embeddings are needed.
            RAW/JPEG versions and near duplicates count together;{" "}
            {taste.conflicting_groups} groups with conflicting feedback
            excluded.
          </p>
          {taste.status === "trained" ? (
            <div className="taste-validation">
              <strong>
                Held-out balanced accuracy:{" "}
                {((taste.heldout_balanced_accuracy ?? 0) * 100).toFixed(1)}%
              </strong>
              <p>
                {taste.training_count} training groups · {taste.heldout_count}{" "}
                held-out groups · profile {taste.version}
              </p>
              <p className="footnote">
                A small internal check on your labels, not proof of future
                quality. At least 60% is required to enable the experimental 30%
                preference blend. Quality floors and manual choices stay
                protected.
              </p>
            </div>
          ) : (
            <p className="footnote">{taste.reason}</p>
          )}
          <div className="form-actions">
            <Button
              variant="outline"
              disabled={
                action.isPending ||
                taste.usable_likes < 10 ||
                taste.usable_dislikes < 10
              }
              onClick={() => action.mutate("train")}
            >
              {action.isPending ? "Updating…" : "Train local profile"}
            </Button>
            {taste.status === "trained" && (
              <Button
                disabled={
                  action.isPending || (!taste.enabled && !taste.eligible)
                }
                onClick={() =>
                  action.mutate(taste.enabled ? "disable" : "enable")
                }
              >
                {taste.enabled
                  ? "Pause personal ranking"
                  : "Apply personal ranking"}
              </Button>
            )}
            <Button
              variant="ghost"
              disabled={action.isPending || !taste.labels}
              onClick={() => setForget(true)}
            >
              Forget my taste data
            </Button>
          </div>
        </>
      )}
      <p className="footnote">
        No cloud training or new model download. The learner uses your cached
        CLIP embeddings and a fixed centroid algorithm. Feedback changes require
        explicit retraining. Affinity is not a probability that you will like a
        picture.
      </p>
      {(result.error || action.error) && (
        <p className="error" role="alert">
          {result.error?.message || action.error?.message}
        </p>
      )}
      {forget && (
        <Modal title="Forget taste feedback" close={() => setForget(false)}>
          <div className="collection-form">
            <p>
              Remove all Like/Dislike labels and the local taste profile across
              every collection? Selections, stars and originals stay untouched.
            </p>
            <div className="form-actions">
              <Button variant="outline" onClick={() => setForget(false)}>
                Cancel
              </Button>
              <Button
                disabled={action.isPending}
                onClick={() => action.mutate("forget")}
              >
                Forget feedback
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </section>
  );
}
