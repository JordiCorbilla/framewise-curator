import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowDownToLine,
  ArrowUp,
  Check,
  ChevronRight,
  Columns2,
  Loader2,
  Plus,
  RotateCcw,
  Star,
  Trophy,
  X,
} from "lucide-react";
import { api } from "../services/api";
import { Button } from "../components/ui/button";
import { active } from "../components/Progress";
import { HighlightBadges, finalistNames } from "../components/HighlightBadges";
import { HighlightPicker } from "../features/curation/HighlightPicker";
import { HighlightSettings } from "../features/curation/HighlightSettings";
import { PhotoCompare } from "../features/curation/PhotoCompare";
import type { HighlightConfig, HighlightsData, Library, Photo } from "../types";

type Picker = {
  purpose: "flickr" | "competition" | "replace" | "compare";
  slot?: number;
};

export function Highlights({
  library,
  open,
  onError,
  onBrowse,
  enrich,
  scanning,
}: {
  library: Library;
  open: (p: Photo, photos: Photo[]) => void;
  onError: (message: string) => void;
  onBrowse: (filter: string) => void;
  enrich: () => void;
  scanning: boolean;
}) {
  const client = useQueryClient();
  const [tab, setTab] = useState<"flickr" | "competition">("competition");
  const [picker, setPicker] = useState<Picker | null>(null);
  const [compareLeft, setCompareLeft] = useState<Photo | null>(null);
  const [pair, setPair] = useState<[Photo, Photo] | null>(null);
  const [message, setMessage] = useState("");
  const [flickrPage, setFlickrPage] = useState(1);
  const result = useQuery({
    queryKey: ["highlights", library.id, flickrPage],
    queryFn: () =>
      api<HighlightsData>(
        `/libraries/${library.id}/highlights?flickr_page=${flickrPage}`,
      ),
    refetchInterval: (query) =>
      active(library.job) ||
      (query.state.data?.status === "waiting" &&
        library.job?.status === "complete")
        ? 2500
        : false,
  });
  const mutation = useMutation({
    mutationFn: ({
      path,
      method,
      data,
    }: {
      path: string;
      method: string;
      data: unknown;
    }) => api<HighlightsData>(path, method, data),
    onSuccess: (data) => {
      client.setQueryData(["highlights", library.id, 1], data);
      setFlickrPage(1);
      for (const key of [
        "libraries",
        "photos",
        "photo",
        "related",
        "highlight-search",
        "highlights",
      ])
        void client.invalidateQueries({ queryKey: [key] });
      setPicker(null);
      setMessage("Saved locally. Your manual choices are protected.");
    },
    onError: (error) => onError(error.message),
  });
  const data = result.data;
  const ready = !!data && data.status === "ready" && !active(library.job);
  const busy = mutation.isPending || !ready;
  const change = (photo: Photo, values: unknown) =>
    mutation.mutate({
      path: `/photos/${photo.id}/highlights`,
      method: "PATCH",
      data: values,
    });
  const replace = (photo: Photo, slot: number) =>
    mutation.mutate({
      path: `/libraries/${library.id}/highlights/finalists/${slot}`,
      method: "PUT",
      data: { photo_id: photo.id },
    });
  const compare = (photo: Photo) => {
    if (compareLeft && compareLeft.id !== photo.id) {
      setPair([compareLeft, photo]);
      setCompareLeft(null);
      setPicker(null);
    } else {
      setCompareLeft(photo);
      setMessage("Choose Compare on a second frame, or browse the collection.");
    }
  };
  const displayed = data
    ? [
        ...new Map(
          [...data.finalists, ...data.flickr, ...data.alternatives].map((p) => [
            p.id,
            p,
          ]),
        ).values(),
      ]
    : [];
  const select = (p: Photo) => {
    if (picker?.purpose === "replace") replace(p, picker.slot!);
    else if (picker?.purpose === "flickr")
      change(p, { flickr: "keep", include_lightroom: !p.selected });
    else if (picker?.purpose === "competition")
      change(p, { competition: "include" });
    else compare(p);
  };
  return (
    <>
      <div className="page-heading highlights-heading">
        <div>
          <div className="eyebrow">THE FRAMES THAT STAY WITH YOU</div>
          <h1>Highlights.</h1>
          <p>A closer look at your strongest work. Your judgement, always.</p>
        </div>
        <div className="highlights-legend">
          <span>
            <Check size={12} />
            Lightroom Pick
          </span>
          <span>
            <Star size={12} />
            Flickr Standout
          </span>
          <span>
            <Trophy size={12} />
            Competition Candidate
          </span>
        </div>
      </div>
      <div
        className="highlights-tabs"
        role="tablist"
        aria-label="Highlights categories"
      >
        {(["flickr", "competition"] as const).map((key) => (
          <button
            key={key}
            role="tab"
            id={`highlights-tab-${key}`}
            aria-selected={tab === key}
            aria-controls={`highlights-panel-${key}`}
            tabIndex={tab === key ? 0 : -1}
            onKeyDown={(e) => {
              if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
                e.preventDefault();
                const next = key === "flickr" ? "competition" : "flickr";
                setTab(next);
                document.getElementById(`highlights-tab-${next}`)?.focus();
              }
            }}
            onClick={() => setTab(key)}
          >
            {key === "flickr" ? <Star size={16} /> : <Trophy size={16} />}
            <span>
              {key === "flickr" ? "Flickr Standouts" : "Competition Top 3"}
            </span>
            <b>
              {ready
                ? key === "flickr"
                  ? data.summary.flickr_count
                  : data.summary.finalist_count
                : "—"}
            </b>
          </button>
        ))}
      </div>
      {result.isPending ? (
        <div className="empty">
          <Loader2 className="animate-spin" />
          Opening your Highlights…
        </div>
      ) : result.error ? (
        <div className="error" role="alert">
          {result.error.message}
          <Button variant="outline" onClick={() => void result.refetch()}>
            Retry
          </Button>
        </div>
      ) : !ready ? (
        <section className="highlights-waiting">
          <Trophy size={30} />
          <h2>Let the full collection have its say.</h2>
          <p>
            {active(library.job)
              ? "Analysis is in progress. Exceptional recommendations are finalised after all eligible frames have been analysed."
              : (data?.summary.reason ??
                "Complete a scan to reveal Highlights.")}
          </p>
          <Button
            variant="outline"
            onClick={enrich}
            disabled={scanning || active(library.job)}
          >
            {scanning ? <Loader2 size={14} className="animate-spin" /> : null}
            Resume collection analysis
          </Button>
        </section>
      ) : (
        <>
          <div className="highlights-context">
            <span>
              GENERAL BEST 3 <span className="subtle-divider">/</span>{" "}
              {data.summary.analysed} analysed{" "}
              <span className="subtle-divider">/</span> {data.summary.viable}{" "}
              independent frames above the quality floor
            </span>
            <span title="Ranking configuration version">
              {data.summary.version} ·{" "}
              {data.summary.configuration_version.slice(0, 8)}
            </span>
          </div>
          {!!data.summary.embedding_missing && (
            <div className="notice embedding-notice">
              <div>
                <strong>
                  Visual embeddings are missing for{" "}
                  {data.summary.embedding_missing} frames.
                </strong>
                <p>
                  Current ranking omits unavailable distinctiveness
                  measurements. Fill the cache using the installed encoder and
                  existing display previews.
                </p>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={enrich}
                disabled={scanning}
              >
                Complete cached analysis
              </Button>
            </div>
          )}
          <div className="highlight-disclaimer">
            Recommendations for human review. These scores do not predict Flickr
            popularity, publication acceptance or competition wins. Theme-based
            judging is not available in V1.
          </div>
          {message && (
            <div className="highlight-status" role="status">
              <span>{message}</span>
              <button
                aria-label="Dismiss Highlights message"
                onClick={() => setMessage("")}
              >
                <X size={14} />
              </button>
            </div>
          )}
          {compareLeft && (
            <div className="compare-prompt">
              <Columns2 size={16} />
              <span>
                Comparing <b>{compareLeft.filename}</b>. Choose another frame.
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPicker({ purpose: "compare" })}
              >
                Browse photographs
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setCompareLeft(null)}
              >
                Cancel
              </Button>
            </div>
          )}
          <section
            role="tabpanel"
            id={`highlights-panel-${tab}`}
            aria-labelledby={`highlights-tab-${tab}`}
          >
            {tab === "competition" ? (
              <>
                <div className="highlight-section-title">
                  <div>
                    <h2>A considered competition shortlist.</h2>
                    <p>
                      {data.finalists.length} of up to 3 finalists ·{" "}
                      {data.summary.forced
                        ? "Exactly three override enabled"
                        : "Quality floors and duplicate suppression applied"}
                    </p>
                  </div>
                  <Button variant="outline" asChild>
                    <a
                      href={`/api/libraries/${library.id}/export/competition_top3.csv`}
                      download
                    >
                      <ArrowDownToLine size={14} />
                      Export Top 3
                    </a>
                  </Button>
                </div>
                {data.finalists.length ? (
                  <div className="podium">
                    {data.finalists.map((p) => (
                      <FinalistCard
                        key={p.id}
                        photo={p}
                        busy={busy}
                        open={() => open(p, displayed)}
                        compare={() => compare(p)}
                        promote={() => replace(p, 1)}
                        replace={() =>
                          setPicker({
                            purpose: "replace",
                            slot: p.highlights!.competition_rank!,
                          })
                        }
                        demote={() => change(p, { competition: "alternative" })}
                        automatic={() => change(p, { competition: "auto" })}
                      />
                    ))}
                  </div>
                ) : (
                  <div className="empty highlights-empty">
                    <Trophy size={32} />
                    <h2>No automatic competition finalists yet.</h2>
                    <p>
                      No independent frames cleared the quality floor. You can
                      include a frame manually or enable the explicit Exactly
                      three override below.
                    </p>
                    <Button
                      variant="outline"
                      onClick={() => setPicker({ purpose: "competition" })}
                    >
                      Include a candidate manually
                    </Button>
                  </div>
                )}
                {data.finalists.length > 0 && data.finalists.length < 3 && (
                  <p className="footnote fewer-finalists">
                    Only {data.finalists.length} independent frames currently
                    qualify. Review the floors or explicitly choose Exactly
                    three in Ranking controls. Manual exclusions remain
                    protected.
                  </p>
                )}
                <div className="highlight-section-title alternatives-heading">
                  <div>
                    <h2>Alternatives</h2>
                    <p>
                      The next independent candidates. Related frames remain
                      available in the lightbox.
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onBrowse("competition_alternatives")}
                    >
                      Browse all
                      <ChevronRight size={13} />
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setPicker({ purpose: "competition" })}
                      disabled={busy}
                    >
                      <Plus size={13} />
                      Include a frame
                    </Button>
                  </div>
                </div>
                <div className="alternatives-grid">
                  {data.alternatives.map((p) => (
                    <article className="alternative-card" key={p.id}>
                      <button
                        className="image-button"
                        onClick={() => open(p, displayed)}
                        aria-label={`Inspect alternative ${p.filename}`}
                      >
                        <img
                          src={p.thumbnail!}
                          alt={p.filename}
                          loading="lazy"
                        />
                      </button>
                      <div>
                        <div className="alternative-heading">
                          <h3>{p.filename}</h3>
                          <b>
                            {p.highlights?.score.toFixed(1)}
                            <small>/100</small>
                          </b>
                        </div>
                        <p>
                          Aesthetic {p.aesthetic?.toFixed(2) ?? "unavailable"} ·
                          technical {p.highlights?.technical.toFixed(1)}
                        </p>
                        <HighlightBadges photo={p} />
                        <div className="alternative-actions">
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={busy}
                            onClick={() => replace(p, 1)}
                          >
                            <ArrowUp size={12} />
                            Make #1
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => compare(p)}
                          >
                            <Columns2 size={12} />
                            Compare
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled={busy}
                            onClick={() => change(p, { competition: "reject" })}
                          >
                            Exclude
                          </Button>
                          {p.highlights?.competition_origin === "manual" && (
                            <Button
                              variant="ghost"
                              size="sm"
                              disabled={busy}
                              onClick={() => change(p, { competition: "auto" })}
                            >
                              Use auto
                            </Button>
                          )}
                        </div>
                      </div>
                    </article>
                  ))}
                </div>
                {!data.alternatives.length && (
                  <p className="footnote">
                    No additional independent candidates cleared the current
                    floors.
                  </p>
                )}
              </>
            ) : (
              <>
                <div className="highlight-section-title">
                  <div>
                    <h2>Flickr Standouts</h2>
                    <p>
                      {data.summary.flickr_count} standouts ·{" "}
                      {(
                        (data.summary.flickr_count /
                          Math.max(library.total, 1)) *
                        100
                      ).toFixed(1)}
                      % of the collection · a subset of your Lightroom Picks
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      onClick={() => setPicker({ purpose: "flickr" })}
                      disabled={busy}
                    >
                      <Plus size={14} />
                      Add manually
                    </Button>
                    <Button asChild>
                      <a
                        href={`/api/libraries/${library.id}/export/flickr_standouts.csv`}
                        download
                      >
                        <ArrowDownToLine size={14} />
                        Export standouts
                      </a>
                    </Button>
                  </div>
                </div>
                <p className="footnote flickr-sort">
                  Sorted by the separate Highlights ranking. Manual additions
                  can exceed the automatic count limit.
                </p>
                {data.flickr.length ? (
                  <div className="standouts-grid">
                    {data.flickr.map((p) => (
                      <article key={p.id} className="standout-card">
                        <button
                          className="image-button"
                          onClick={() => open(p, displayed)}
                          aria-label={`Inspect standout ${p.filename}`}
                        >
                          <img
                            src={p.thumbnail!}
                            alt={p.filename}
                            loading="lazy"
                          />
                        </button>
                        <div className="standout-body">
                          <HighlightBadges photo={p} />
                          <div className="alternative-heading">
                            <h3>{p.filename}</h3>
                            <b>
                              {p.highlights?.score.toFixed(1)}
                              <small>/100</small>
                            </b>
                          </div>
                          <p>
                            Aesthetic {p.aesthetic?.toFixed(2)} /10 · technical{" "}
                            {p.highlights?.technical.toFixed(1)} /100
                          </p>
                          <p className="footnote">
                            {p.highlights?.group_rank === 1
                              ? "Highest Highlights score in its similarity group or an independent frame."
                              : `Highlights group rank ${p.highlights?.group_rank}; inspect the related alternatives.`}
                          </p>
                          <div className="alternative-actions">
                            <Button
                              variant="outline"
                              size="sm"
                              disabled={busy}
                              onClick={() => change(p, { flickr: "keep" })}
                            >
                              <Check size={12} />
                              {p.highlights?.flickr_origin === "manual"
                                ? "Kept by you"
                                : "Keep"}
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              disabled={busy}
                              onClick={() => change(p, { flickr: "reject" })}
                            >
                              Reject
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => compare(p)}
                            >
                              <Columns2 size={12} />
                              Compare
                            </Button>
                            {p.highlights?.flickr_origin === "manual" && (
                              <Button
                                variant="ghost"
                                size="sm"
                                disabled={busy}
                                onClick={() => change(p, { flickr: "auto" })}
                              >
                                Use auto
                              </Button>
                            )}
                          </div>
                        </div>
                      </article>
                    ))}
                  </div>
                ) : (
                  <div className="empty highlights-empty">
                    <Star size={32} />
                    <h2>
                      {flickrPage === 1
                        ? "No automatic standouts cleared these thresholds."
                        : "No standouts on this page."}
                    </h2>
                    <p>
                      Review the quality controls or add a Lightroom pick
                      manually. Every collection does not need an exceptional
                      recommendation.
                    </p>
                  </div>
                )}
              </>
            )}
          </section>
          {tab === "flickr" && data.summary.flickr_count > 48 && (
            <div className="pagination">
              <span>
                Page {flickrPage} of {Math.ceil(data.summary.flickr_count / 48)}{" "}
                · 48 per page
              </span>
              <div>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={flickrPage === 1}
                  onClick={() => setFlickrPage(flickrPage - 1)}
                >
                  Previous standouts
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={flickrPage * 48 >= data.summary.flickr_count}
                  onClick={() => setFlickrPage(flickrPage + 1)}
                >
                  Next standouts
                </Button>
              </div>
            </div>
          )}
          <HighlightSettings
            key={`${library.id}-${data.summary.configuration_version}`}
            config={data.config}
            busy={busy}
            save={(config: HighlightConfig) =>
              mutation.mutate({
                path: `/libraries/${library.id}/highlights/config`,
                method: "PATCH",
                data: config,
              })
            }
          />
        </>
      )}
      {picker && (
        <HighlightPicker
          libraryId={library.id}
          purpose={picker.purpose}
          title={
            picker.purpose === "replace"
              ? `Replace competition rank #${picker.slot}`
              : picker.purpose === "flickr"
                ? "Add a Flickr Standout"
                : picker.purpose === "competition"
                  ? "Include a competition candidate"
                  : "Choose a frame to compare"
          }
          close={() => setPicker(null)}
          choose={select}
          busy={mutation.isPending}
          excludeId={picker.purpose === "compare" ? compareLeft?.id : undefined}
        />
      )}
      {pair && (
        <PhotoCompare
          left={pair[0]}
          right={pair[1]}
          close={() => setPair(null)}
        />
      )}
    </>
  );
}

function FinalistCard({
  photo: p,
  busy,
  open,
  compare,
  promote,
  replace,
  demote,
  automatic,
}: {
  photo: Photo;
  busy: boolean;
  open: () => void;
  compare: () => void;
  promote: () => void;
  replace: () => void;
  demote: () => void;
  automatic: () => void;
}) {
  const h = p.highlights!,
    rank = h.competition_rank!;
  return (
    <article className={`podium-card medal-border-${rank}`}>
      <div className={`podium-title medal-text-${rank}`}>
        <Trophy size={rank === 1 ? 21 : 17} />
        <h3>
          #{rank} — {finalistNames[rank - 1]}
        </h3>
        <span>
          {h.competition_origin === "manual" ? "YOUR CHOICE" : "AI ASSISTED"}
        </span>
      </div>
      <button
        className="podium-image"
        onClick={open}
        aria-label={`Inspect finalist ${p.filename}`}
      >
        <img src={p.preview!} alt={p.filename} />
      </button>
      <div className="podium-body">
        <div className="podium-filename">
          <h3>{p.filename}</h3>
          <strong>
            {h.score.toFixed(1)}
            <small>/100</small>
          </strong>
        </div>
        <p className="relative-label">
          Relative Highlights score · not a winning probability
        </p>
        {p.raw_filename && p.raw_filename !== p.filename && (
          <p className="raw-handoff">
            Lightroom handoff → {p.raw_filename}. This edited preview supplied
            the analysis.
          </p>
        )}
        <HighlightBadges photo={p} />
        <div className="evidence-block">
          <h4>Measured evidence</h4>
          <ul>
            {h.strengths.map((text) => (
              <li key={text}>{text}</li>
            ))}
          </ul>
          {h.diversity_adjustment > 0 && (
            <p>
              Visual redundancy adjustment: −{h.diversity_adjustment.toFixed(1)}{" "}
              points during finalist selection.
            </p>
          )}
        </div>
        <details className="uncertainties" open={rank === 1}>
          <summary>Uncertainties & limits</summary>
          <ul>
            {h.uncertainties.map((text) => (
              <li key={text}>{text}</li>
            ))}
          </ul>
        </details>
        <div className="podium-actions">
          {rank !== 1 && (
            <Button
              variant="outline"
              size="sm"
              disabled={busy}
              onClick={promote}
            >
              <ArrowUp size={12} />
              Promote to #1
            </Button>
          )}
          <Button variant="outline" size="sm" disabled={busy} onClick={replace}>
            Replace #{rank}
          </Button>
          <Button variant="ghost" size="sm" onClick={compare}>
            <Columns2 size={12} />
            Compare
          </Button>
          <Button variant="ghost" size="sm" disabled={busy} onClick={demote}>
            Demote
          </Button>
          {h.competition_origin === "manual" && (
            <Button
              variant="ghost"
              size="sm"
              disabled={busy}
              onClick={automatic}
            >
              <RotateCcw size={12} />
              Use auto
            </Button>
          )}
        </div>
      </div>
    </article>
  );
}
