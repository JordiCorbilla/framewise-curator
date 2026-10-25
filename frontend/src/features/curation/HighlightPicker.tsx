import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Search } from "lucide-react";
import { api } from "../../services/api";
import { Modal } from "../../components/Modal";
import { Button } from "../../components/ui/button";
import { HighlightBadges } from "../../components/HighlightBadges";
import type { Photo, Photos } from "../../types";

export function HighlightPicker({
  libraryId,
  title,
  close,
  choose,
  busy,
  purpose,
  excludeId,
}: {
  libraryId: string;
  title: string;
  close: () => void;
  choose: (p: Photo) => void;
  busy: boolean;
  purpose: "flickr" | "competition" | "replace" | "compare";
  excludeId?: string;
}) {
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const photos = useQuery({
    queryKey: ["highlight-search", libraryId, q, page],
    queryFn: () =>
      api<Photos>(
        `/libraries/${libraryId}/highlights/search?q=${encodeURIComponent(q)}&page=${page}`,
      ),
  });
  return (
    <Modal title={title} close={close}>
      <div className="picker-body">
        <label className="picker-search">
          <Search size={15} />
          <input
            autoFocus
            aria-label="Search photographs by filename"
            placeholder="Find an original filename…"
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setPage(1);
            }}
          />
        </label>
        <p className="footnote">
          {purpose === "flickr"
            ? "Manually adding a standout also keeps it for Lightroom when needed. It can bypass the automatic quality threshold."
            : purpose === "replace"
              ? "Your choice replaces this slot. The displaced finalist stays available as an alternative; other finalists remain in place."
              : purpose === "competition"
                ? "Include a frame for manual competition review, even below the automatic quality floor."
                : "Choose a second frame to compare measured features."}
        </p>
        {photos.error && <p className="error">{photos.error.message}</p>}
        <div className="picker-results">
          {photos.isPending ? (
            <p>Loading photographs…</p>
          ) : (
            photos.data?.items.map((p) => (
              <article key={p.id}>
                <img src={p.thumbnail!} alt={p.filename} loading="lazy" />
                <div>
                  <strong>{p.filename}</strong>
                  <small>
                    Aesthetic {p.aesthetic?.toFixed(2) ?? "unavailable"} · rank
                    proxy {p.highlights?.score.toFixed(1) ?? "—"}
                  </small>
                  <HighlightBadges photo={p} />
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={busy || p.id === excludeId}
                  onClick={() => choose(p)}
                >
                  {purpose === "flickr"
                    ? p.selected
                      ? "Add standout"
                      : "Standout + keep"
                    : purpose === "compare"
                      ? "Compare"
                      : purpose === "replace"
                        ? "Replace"
                        : "Include candidate"}
                </Button>
              </article>
            ))
          )}
        </div>
        <div className="pagination">
          <span>
            {photos.data?.total ?? 0} photographs · page {page}
          </span>
          <div>
            <Button
              variant="outline"
              size="sm"
              disabled={page === 1}
              onClick={() => setPage(page - 1)}
              aria-label="Previous search page"
            >
              <ChevronLeft size={15} />
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={!photos.data || page * 24 >= photos.data.total}
              onClick={() => setPage(page + 1)}
              aria-label="Next search page"
            >
              <ChevronRight size={15} />
            </Button>
          </div>
        </div>
      </div>
    </Modal>
  );
}
