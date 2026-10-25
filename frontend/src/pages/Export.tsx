import { useQuery } from "@tanstack/react-query";
import { ArrowDownToLine, CircleHelp } from "lucide-react";
import type { Library } from "../types";
import { Button } from "../components/ui/button";
import { api } from "../services/api";
import type { HighlightsData } from "../types";
export function Export({ library }: { library: Library }) {
  const highlights = useQuery({
    queryKey: ["highlights", library.id],
    queryFn: () => api<HighlightsData>(`/libraries/${library.id}/highlights`),
  });
  const xmp = useQuery({
    queryKey: ["xmp", library.id],
    queryFn: () =>
      api<{ reason: string; conflicts: string[] }>(
        `/libraries/${library.id}/xmp/preview`,
      ),
  });
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">MAKE ROOM FOR THE EDIT</div>
          <h1>From shortlist to Lightroom.</h1>
          <p>
            {library.selected} selected photographs. Your original RAW files,
            ready for the next step.
          </p>
        </div>
      </div>
      <div className="export-layout">
        <div className="export-options">
          <section className="export-card">
            <div className="flex items-center gap-3">
              <ArrowDownToLine size={22} />
              <h2>Export your curation</h2>
            </div>
            <p>
              UTF-8 CSV files include original paths, measured scores,
              recommendations, decisions, ratings and similarity groups.
            </p>
            <Button asChild>
              <a
                href={`/api/libraries/${library.id}/export/selected_photos.csv`}
                download
              >
                <ArrowDownToLine size={15} />
                Selected photographs · CSV
              </a>
            </Button>
            <Button variant="outline" asChild>
              <a
                href={`/api/libraries/${library.id}/export/all_photos.csv`}
                download
              >
                All photographs · CSV
              </a>
            </Button>
            <p className="footnote">
              No photographs are copied. Exports point to your original files.
            </p>
          </section>
          <section className="export-card">
            <h2>Three levels of selection</h2>
            <p>
              Independent Lightroom, Flickr and competition recommendations.
              Each CSV includes original paths, ranks, measured evidence, manual
              overrides and version provenance.
            </p>
            {[
              ["lightroom_picks.csv", "Lightroom Picks", library.selected],
              [
                "flickr_standouts.csv",
                "Flickr Standouts",
                highlights.data?.summary.flickr_count,
              ],
              [
                "competition_top3.csv",
                "Competition Top 3",
                highlights.data?.summary.finalist_count,
              ],
              [
                "competition_alternatives.csv",
                "Competition alternatives",
                highlights.data?.summary.alternatives?.length,
              ],
            ].map(([file, label, count]) =>
              file === "lightroom_picks.csv" ||
              highlights.data?.status === "ready" ? (
                <Button key={file} variant="outline" asChild>
                  <a
                    href={`/api/libraries/${library.id}/export/${file}`}
                    download
                  >
                    <ArrowDownToLine size={14} />
                    {label} · {count ?? 0} · CSV
                  </a>
                </Button>
              ) : (
                <Button key={file} variant="outline" disabled>
                  {label} · finish analysis first
                </Button>
              ),
            )}
            {highlights.error && (
              <p className="error">{highlights.error.message}</p>
            )}
            <p className="footnote">
              Verified edited-JPEG / NEF pairs point to the original NEF.
              Analysis filenames and provenance remain in the CSV. Unpaired
              rasters keep their own original path. Each row is a
              recommendation; a RAW path may repeat when multiple versions were
              manually selected. No Flickr uploads or competition submissions
              are performed.
            </p>
          </section>
          <section className="export-card disabled-card">
            <div className="flex items-center justify-between">
              <h2>Lightroom XMP sidecars</h2>
              <span className="file-tag">DEFERRED</span>
            </div>
            <p>
              {xmp.data?.reason ??
                "Sidecar writing is disabled pending Lightroom metadata round-trip validation."}
            </p>
            {xmp.error && <p className="error">{xmp.error.message}</p>}
            <Button variant="outline" disabled>
              Write XMP sidecars
            </Button>
            <p className="footnote">
              {xmp.data?.conflicts.length ?? 0} existing sidecars detected. No
              changes made.
            </p>
          </section>
        </div>
        <section className="lightroom-guide">
          <div className="eyebrow">LIGHTROOM CLASSIC HANDOFF</div>
          <h2>Your edit starts here.</h2>
          <ol>
            <li>
              <b>Download selected_photos.csv.</b>
              <p>
                Open it in a spreadsheet to review the exact original file paths
                and your shortlist.
              </p>
            </li>
            <li>
              <b>Import the original RAW files.</b>
              <p>
                In Lightroom Classic, use File → Import Photos and Video. Choose
                Add to keep photographs in their current location.
              </p>
            </li>
            <li>
              <b>Use the shortlist as your reference.</b>
              <p>
                Find selected filenames in Lightroom and add them to a
                Collection or apply your own star ratings.
              </p>
            </li>
          </ol>
          <div className="notice">
            <CircleHelp size={18} />
            <p>
              Lightroom Classic does not turn a CSV into a Collection
              automatically. Already-catalogued images may need metadata
              synchronisation if you later use tested XMP sidecars.
            </p>
          </div>
          <p className="footnote">
            Automatic copy-to-folder export and a Lightroom plugin are outside
            V1.
          </p>
        </section>
      </div>
    </>
  );
}
