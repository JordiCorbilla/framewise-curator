import { Star, Trophy } from "lucide-react";
import type { Photo } from "../types";

// eslint-disable-next-line react-refresh/only-export-components
export const finalistNames = ["Best Shot", "Runner-Up", "Third Pick"];
export function HighlightBadges({ photo }: { photo: Photo }) {
  const h = photo.highlights;
  if (!h) return null;
  return (
    <div className="highlight-badges">
      {h.competition_rank && (
        <span className={`medal medal-${h.competition_rank}`}>
          <Trophy size={12} />#{h.competition_rank} ·{" "}
          {finalistNames[h.competition_rank - 1]}
        </span>
      )}
      {h.flickr && (
        <span className="standout-badge">
          <Star size={11} />
          Flickr Standout
        </span>
      )}
    </div>
  );
}
