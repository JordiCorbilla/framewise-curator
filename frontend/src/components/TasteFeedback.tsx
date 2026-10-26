import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ThumbsUp, ThumbsDown, RotateCcw } from "lucide-react";
import { api } from "../services/api";

export function TasteFeedback({ photoId }: { photoId: string }) {
  const client = useQueryClient();
  const label = useQuery({
    queryKey: ["taste-label", photoId],
    queryFn: () => api<{ value: number }>(`/photos/${photoId}/taste`),
  });
  const save = useMutation({
    mutationFn: (value: number) =>
      api<{ value: number }>(`/photos/${photoId}/taste`, "PATCH", { value }),
    onSuccess: (data) => {
      client.setQueryData(["taste-label", photoId], data);
      for (const key of ["taste", "libraries", "photos", "photo", "highlights"])
        void client.invalidateQueries({ queryKey: [key] });
    },
  });
  return (
    <section className="taste-feedback">
      <h3>My taste</h3>
      <p className="footnote">
        Teach your local preference profile. Separate from Keep and star
        ratings. Changing feedback pauses the old model until you retrain.
      </p>
      <div className="taste-buttons">
        <button
          aria-label="I like this photo"
          aria-pressed={label.data?.value === 1}
          disabled={save.isPending || label.isPending}
          onClick={() => save.mutate(1)}
        >
          <ThumbsUp size={15} />
          Like
        </button>
        <button
          aria-label="I dislike this photo"
          aria-pressed={label.data?.value === -1}
          disabled={save.isPending || label.isPending}
          onClick={() => save.mutate(-1)}
        >
          <ThumbsDown size={15} />
          Dislike
        </button>
        {!!label.data?.value && (
          <button
            aria-label="Clear taste feedback"
            disabled={save.isPending}
            onClick={() => save.mutate(0)}
          >
            <RotateCcw size={13} />
            Clear
          </button>
        )}
      </div>
      {(save.error || label.error) && (
        <p className="error" role="alert">
          {save.error?.message || label.error?.message}
        </p>
      )}
    </section>
  );
}
