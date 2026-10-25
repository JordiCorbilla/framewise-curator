import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Aperture,
  ChevronLeft,
  ChevronRight,
  Grid2X2,
  SlidersHorizontal,
} from "lucide-react";
import { Button } from "../../components/ui/button";
import { PhotoCard } from "../../components/PhotoCard";
import { active } from "../../components/Progress";
import { api } from "../../services/api";
import type { Library, Photo, Photos } from "../../types";
export function Budget({
  library,
  refresh,
  onError,
}: {
  library: Library;
  refresh: () => void;
  onError: (s: string) => void;
}) {
  const [draft, setDraft] = useState<number | null>(null);
  const update = useMutation({
    mutationFn: (budget: number) =>
      api(`/libraries/${library.id}/budget`, "PATCH", { budget }),
    onSuccess: () => {
      setDraft(null);
      refresh();
    },
    onError: (e) => onError(e.message),
  });
  const value = draft ?? library.budget;
  return (
    <section className="budget-panel">
      <div>
        <SlidersHorizontal size={17} />
        <div>
          <strong>Selection budget</strong>
          <p>A little more focus. Room for your judgement.</p>
        </div>
      </div>
      <div className="budget-slider">
        <span>Selective</span>
        <input
          aria-label="Selection budget percentage"
          type="range"
          min={1}
          max={100}
          value={value}
          onChange={(e) => setDraft(Number(e.target.value))}
        />
        <span>Inclusive</span>
        <b>{value}%</b>
        {draft !== null && (
          <Button
            size="sm"
            onClick={() => update.mutate(value)}
            disabled={update.isPending}
          >
            Apply
          </Button>
        )}
      </div>
      <span className="budget-hint">Manual decisions protected</span>
    </section>
  );
}

export function Gallery({
  library,
  selected,
  decide,
  open,
  initialFilter,
}: {
  library: Library;
  selected: boolean;
  decide: (
    id: string,
    data: Partial<Pick<Photo, "decision" | "stars">>,
  ) => void;
  open: (p: Photo, items: Photo[]) => void;
  initialFilter?: string;
}) {
  const [filter, setFilter] = useState(
    selected ? "selected" : (initialFilter ?? "all"),
  );
  const [sort, setSort] = useState(
    initialFilter === "competition"
      ? "competition"
      : initialFilter &&
          ["flickr", "competition_alternatives"].includes(initialFilter)
        ? "highlights"
        : "score",
  );
  const [page, setPage] = useState(1);
  const result = useQuery({
    queryKey: ["photos", library.id, filter, sort, page],
    queryFn: () =>
      api<Photos>(
        `/libraries/${library.id}/photos?filter=${filter}&sort=${sort}&page=${page}`,
      ),
    refetchInterval: active(library.job) ? 3500 : false,
  });
  const filters = selected
    ? [
        ["selected", "Lightroom Picks"],
        ["ai", "AI recommendations"],
        ["manual", "My picks"],
      ]
    : [
        ["all", "All Photos"],
        ["ai", "AI Picks"],
        ["lightroom", "Lightroom Picks"],
        ["flickr", "Flickr Standouts"],
        ["competition", "Competition Top 3"],
        ["competition_alternatives", "Other candidates"],
        ["manual", "My Picks"],
        ["review", "Review"],
        ["low", "Low Priority"],
        ["similar", "Similar / Bursts"],
        ["failed", "Unprocessed / Failed"],
      ];
  const pages = Math.max(1, Math.ceil((result.data?.total ?? 0) / 48));
  return (
    <>
      <div className="gallery-toolbar">
        <div className="filter-tabs" role="group" aria-label="Photo filters">
          {filters.map(([key, text]) => (
            <button
              key={key}
              className={filter === key ? "active" : ""}
              onClick={() => {
                setFilter(key);
                if (key === "competition") setSort("competition");
                if (["flickr", "competition_alternatives"].includes(key))
                  setSort("highlights");
                setPage(1);
              }}
            >
              {text}
            </button>
          ))}
        </div>
        <label className="sort-control">
          Sort{" "}
          <select
            aria-label="Sort photographs"
            value={sort}
            onChange={(e) => {
              setSort(e.target.value);
              setPage(1);
            }}
          >
            <option value="score">Highest score</option>
            <option value="date">Capture date</option>
            <option value="filename">Filename</option>
            <option value="sharpness">Sharpness</option>
            <option value="aesthetic">Aesthetic model</option>
            <option value="highlights">Highlights rank score</option>
            <option value="competition">Competition rank</option>
          </select>
        </label>
      </div>
      <div className="gallery-count">
        <span>
          {result.data?.total ?? 0} photographs
          {selected && filter === "ai" ? " · before manual overrides" : ""}
        </span>
        <span>
          <Grid2X2 size={13} />
          48 per page
        </span>
      </div>
      {result.error ? (
        <div className="error">
          {result.error.message}
          <Button variant="outline" onClick={() => void result.refetch()}>
            Retry
          </Button>
        </div>
      ) : result.isPending ? (
        <div className="photo-grid">
          {Array.from({ length: 8 }, (_, i) => (
            <div key={i} className="skeleton" />
          ))}
        </div>
      ) : !result.data?.items.length ? (
        <div className="empty">
          <Aperture size={36} strokeWidth={1} />
          <h2>
            {active(library.job)
              ? "Your photographs are on their way."
              : "No photographs in this view."}
          </h2>
          <p>
            {active(library.job)
              ? "Previews appear after each small processing batch."
              : "Try a different filter or adjust your selection."}
          </p>
        </div>
      ) : (
        <div className="photo-grid">
          {result.data.items.map((photo) => (
            <PhotoCard
              key={photo.id}
              photo={photo}
              open={() => open(photo, result.data.items)}
              decide={decide}
            />
          ))}
        </div>
      )}
      <div className="pagination">
        <span>
          Page {page} of {pages}
        </span>
        <div>
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage(page - 1)}
          >
            <ChevronLeft size={15} />
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= pages}
            onClick={() => setPage(page + 1)}
          >
            Next
            <ChevronRight size={15} />
          </Button>
        </div>
      </div>
    </>
  );
}
