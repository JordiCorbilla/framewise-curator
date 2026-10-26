import { useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Check,
  ChevronLeft,
  ChevronRight,
  RotateCcw,
  Star,
  X,
  ZoomIn,
  Layers,
} from "lucide-react";
import { useState } from "react";
import { api } from "../services/api";
import type { Photo, Photos } from "../types";
import { Button } from "./ui/button";
import { HighlightBadges } from "./HighlightBadges";
import { TasteFeedback } from "./TasteFeedback";

function Metric({
  name,
  value,
  suffix = "/100",
}: {
  name: string;
  value?: number | null;
  suffix?: string;
}) {
  return (
    <div className="metric">
      <div>
        <span>{name}</span>
        <b>{value == null ? "Unavailable" : `${value.toFixed(1)} ${suffix}`}</b>
      </div>
      <div className="metric-track">
        <div
          style={{
            width: `${value == null ? 0 : suffix === "/10" ? value * 10 : value}%`,
          }}
        />
      </div>
    </div>
  );
}
export function PhotoViewer({
  photo: initial,
  items,
  close,
  navigate,
  decide,
}: {
  photo: Photo;
  items: Photo[];
  close: () => void;
  navigate: (p: Photo) => void;
  decide: (
    id: string,
    data: Partial<Pick<Photo, "decision" | "stars">>,
  ) => void;
}) {
  const { data: photo } = useQuery({
    queryKey: ["photo", initial.id],
    queryFn: () => api<Photo>(`/photos/${initial.id}`),
    initialData: initial,
  });
  const [zoom, setZoom] = useState(false);
  const panel = useRef<HTMLDivElement>(null);
  const related = useQuery({
    queryKey: ["related", photo.id],
    queryFn: () =>
      api<Photos>(
        `/libraries/${photo.library_id}/photos?group_id=${photo.group_id}&limit=100`,
      ),
    enabled: !!photo.group_id,
  });
  const index = items.findIndex((p) => p.id === photo.id);
  const move = (step: number) => {
    const next = items[index + step];
    if (next) {
      setZoom(false);
      navigate(next);
    }
  };
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    panel.current?.focus();
    const saved = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = saved;
      previous?.focus();
    };
  }, []);
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.target instanceof HTMLInputElement) return;
      if (event.target instanceof HTMLTextAreaElement || event.target instanceof HTMLSelectElement) return;
      if (event.key === " " && event.target instanceof HTMLElement && event.target.closest("button,a,summary")) return;
      if (event.key === "Tab") {
        const focusable = panel.current?.querySelectorAll<HTMLElement>(
          'button:not(:disabled),a[href],[tabindex="0"]',
        );
        if (!focusable?.length) return;
        const first = focusable[0],
          last = focusable[focusable.length - 1];
        if (
          event.shiftKey &&
          (document.activeElement === first ||
            document.activeElement === panel.current)
        ) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
        return;
      }
      if (
        [
          "ArrowLeft",
          "ArrowRight",
          " ",
          "p",
          "P",
          "x",
          "X",
          "u",
          "U",
          "Escape",
          "1",
          "2",
          "3",
          "4",
          "5",
        ].includes(event.key)
      )
        event.preventDefault();
      if (event.key === "Escape") close();
      if (event.key === "ArrowLeft") move(-1);
      if (event.key === "ArrowRight") move(1);
      if ([" ", "p", "P"].includes(event.key))
        decide(photo.id, {
          decision: photo.decision === "keep" ? "auto" : "keep",
        });
      if (["x", "X"].includes(event.key))
        decide(photo.id, { decision: "reject" });
      if (["u", "U"].includes(event.key))
        decide(photo.id, { decision: "auto" });
      if (/^[1-5]$/.test(event.key))
        decide(photo.id, { stars: Number(event.key) });
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  });
  return (
    <div className="viewer-backdrop" onClick={close}>
      <div
        ref={panel}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label={`Inspect ${photo.filename}`}
        className="viewer"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="viewer-header">
          <span>
            {photo.filename}{" "}
            <small>
              {index >= 0
                ? `${index + 1} of ${items.length} on this page`
                : "Related frame"}
            </small>
          </span>
          <div className="flex gap-2">
            <Button
              size="icon"
              variant="ghost"
              aria-label="Previous photograph"
              onClick={() => move(-1)}
              disabled={index <= 0}
            >
              <ChevronLeft size={20} />
            </Button>
            <Button
              size="icon"
              variant="ghost"
              aria-label="Next photograph"
              onClick={() => move(1)}
              disabled={index < 0 || index >= items.length - 1}
            >
              <ChevronRight size={20} />
            </Button>
            <Button
              size="icon"
              variant="ghost"
              aria-label="Close viewer"
              onClick={close}
            >
              <X size={20} />
            </Button>
          </div>
        </header>
        <div className="viewer-body">
          <div className={`viewer-stage ${zoom ? "zoomed" : ""}`}>
            {photo.preview ? (
              <button
                onClick={() => setZoom(!zoom)}
                aria-label={zoom ? "Fit photograph" : "Enlarge cached preview"}
              >
                <img src={photo.preview} alt={photo.filename} />
              </button>
            ) : (
              <p>{photo.error || "Preview pending"}</p>
            )}
            <span className="preview-caption">
              <ZoomIn size={13} />
              {zoom
                ? "Enlarged preview · click to fit"
                : `${photo.width} × ${photo.height} source preview · click to enlarge`}
            </span>
          </div>
          <aside className="viewer-details">
            <TasteFeedback key={photo.id} photoId={photo.id} />
            <div className="eyebrow">FRAME ASSESSMENT</div>
            <HighlightBadges photo={photo} />
            <div className="detail-score">
              {photo.score?.toFixed(1) ?? "—"}
              <span>/ 100</span>
            </div>
            <p className="sage">
              {photo.selected
                ? "Selected for editing"
                : photo.decision === "reject"
                  ? "Excluded by you"
                  : "Available for review"}
            </p>
            <p className="explanation">{photo.explanation}</p>
            <Metric
              name="Aesthetic model"
              value={photo.aesthetic}
              suffix="/10"
            />
            {photo.taste_affinity != null && (
              <Metric
                name="Your taste affinity (experimental)"
                value={photo.taste_affinity}
              />
            )}
            <Metric
              name="Sharpness / detail"
              value={photo.calibrated.sharpness}
            />
            <Metric name="Tonal quality" value={photo.calibrated.exposure} />
            <p className="footnote">
              Heuristic ranking, not a probability of success. JPEG clipping
              does not prove unrecoverable RAW detail.
            </p>
            <div className="clipping">
              <span>
                Highlights clipped{" "}
                <b>{((photo.raw.highlight_clipping ?? 0) * 100).toFixed(2)}%</b>
              </span>
              <span>
                Shadows clipped{" "}
                <b>{((photo.raw.shadow_clipping ?? 0) * 100).toFixed(2)}%</b>
              </span>
            </div>
            <div className="decision-actions">
              <Button
                onClick={() =>
                  decide(photo.id, {
                    decision: photo.decision === "keep" ? "auto" : "keep",
                  })
                }
              >
                <Check size={15} />
                {photo.decision === "keep" ? "Kept by you" : "Keep"}{" "}
                <kbd>P</kbd>
              </Button>
              <Button
                variant="outline"
                onClick={() => decide(photo.id, { decision: "reject" })}
              >
                <X size={15} />
                Exclude <kbd>X</kbd>
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => decide(photo.id, { decision: "review" })}
              >
                Review later
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => decide(photo.id, { decision: "auto" })}
              >
                <RotateCcw size={12} />
                Reset <kbd>U</kbd>
              </Button>
            </div>
            <div className="detail-stars">
              {[1, 2, 3, 4, 5].map((n) => (
                <button
                  key={n}
                  aria-label={`${n} stars`}
                  onClick={() =>
                    decide(photo.id, { stars: photo.stars === n ? 0 : n })
                  }
                >
                  <Star
                    size={22}
                    fill={photo.stars >= n ? "currentColor" : "none"}
                  />
                </button>
              ))}
            </div>
            {photo.group_id && (
              <section className="related">
                <h3>
                  <Layers size={14} />
                  Related frames · {photo.group_count}
                </h3>
                {photo.group_protected && (
                  <p className="footnote">
                    Possible bracket or uncertain sequence. Review every
                    alternative.
                  </p>
                )}
                <div>
                  {related.data?.items.map((p) => (
                    <button
                      key={p.id}
                      className={p.id === photo.id ? "current" : ""}
                      onClick={() => {
                        setZoom(false);
                        navigate(p);
                      }}
                      aria-label={`View related ${p.filename}`}
                    >
                      <img src={p.thumbnail!} alt={p.filename} />
                      <span>
                        #{p.group_rank} · {p.score?.toFixed(1)}
                      </span>
                    </button>
                  ))}
                </div>
              </section>
            )}
            {photo.highlights && (
              <section className="lightbox-highlights">
                <h3>Highlights evidence</h3>
                <p className="footnote">
                  Relative Highlights rank score{" "}
                  {photo.highlights.score.toFixed(1)}/100. This is separate from
                  the ordinary curation score above.
                </p>
                <ul>
                  {photo.highlights.strengths.map((text) => (
                    <li key={text}>{text}</li>
                  ))}
                </ul>
                <details>
                  <summary>Measured weaknesses & uncertainties</summary>
                  <ul>
                    {photo.highlights.uncertainties.map((text) => (
                      <li key={text}>{text}</li>
                    ))}
                  </ul>
                </details>
              </section>
            )}
            <section className="exif">
              <h3>Capture details</h3>
              {[
                "Model",
                "LensModel",
                "DateTimeOriginal",
                "ExposureTime",
                "FNumber",
                "ISO",
                "FocalLength",
                "ExposureCompensation",
              ]
                .filter((key) => photo.metadata[key] !== undefined)
                .map((key) => (
                  <div key={key}>
                    <span>
                      {(
                        {
                          Model: "Camera",
                          LensModel: "Lens",
                          DateTimeOriginal: "Captured",
                          ExposureTime: "Shutter (s)",
                          FNumber: "Aperture",
                          FocalLength: "Focal length (mm)",
                          ExposureCompensation: "Exposure bias",
                        } as Record<string, string>
                      )[key] ?? key}
                    </span>
                    <b>{String(photo.metadata[key])}</b>
                  </div>
                ))}
              <p className="footnote">
                Analysis source: {photo.provenance ?? "not processed"}. Display
                cache is limited to 2560px; this is not sensor-level 100%
                inspection.
              </p>
            </section>
          </aside>
        </div>
        <footer className="viewer-footer">
          ← → Navigate this page{" "}
          <span> P Keep · X Exclude · U Reset · 1–5 Rate · Esc Close</span>
        </footer>
      </div>
    </div>
  );
}
