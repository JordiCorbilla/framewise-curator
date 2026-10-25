import { useQuery } from "@tanstack/react-query";
import { api } from "../../services/api";
import { Modal } from "../../components/Modal";
import { HighlightBadges } from "../../components/HighlightBadges";
import type { Photo } from "../../types";

export function PhotoCompare({
  left,
  right,
  close,
}: {
  left: Photo;
  right: Photo;
  close: () => void;
}) {
  const pair = useQuery({
    queryKey: ["compare", left.id, right.id],
    queryFn: () =>
      api<{ phash_distance: number | null; cosine_similarity: number | null }>(
        `/libraries/${left.library_id}/highlights/compare?left=${left.id}&right=${right.id}`,
      ),
  });
  const metrics = [
    {
      name: "Aesthetic model output /10",
      values: [left.aesthetic, right.aesthetic],
    },
    {
      name: "Measured detail proxy /100",
      values: [left.calibrated.sharpness, right.calibrated.sharpness],
    },
    {
      name: "Measured tonal proxy /100",
      values: [left.calibrated.exposure, right.calibrated.exposure],
    },
    {
      name: "Preview highlight clipping %",
      values: [
        (left.raw.highlight_clipping ?? 0) * 100,
        (right.raw.highlight_clipping ?? 0) * 100,
      ],
    },
    {
      name: "Heuristic relative rank /100",
      values: [left.highlights?.score, right.highlights?.score],
    },
  ];
  return (
    <Modal title="Compare photographs" close={close} wide>
      <div className="comparison-images">
        {[left, right].map((p) => (
          <section key={p.id}>
            <div className="comparison-image">
              <img src={p.preview!} alt={p.filename} />
            </div>
            <h3>{p.filename}</h3>
            <HighlightBadges photo={p} />
          </section>
        ))}
      </div>
      <div className="comparison-details">
        <h3>Model output & measured preview features</h3>
        <table>
          <thead>
            <tr>
              <th>Signal</th>
              <th>{left.filename}</th>
              <th>{right.filename}</th>
            </tr>
          </thead>
          <tbody>
            {metrics.map((m) => (
              <tr key={m.name}>
                <th>{m.name}</th>
                {m.values.map((v, i) => (
                  <td key={i}>{v == null ? "Unavailable" : v.toFixed(2)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        <p className="footnote">
          Perceptual-hash distance:{" "}
          {pair.data?.phash_distance == null
            ? "unavailable"
            : `${pair.data.phash_distance}/64`}
          . CLIP cosine similarity:{" "}
          {pair.data?.cosine_similarity == null
            ? "unavailable"
            : pair.data.cosine_similarity.toFixed(4)}
          .
        </p>
        {pair.error && <p className="error">{pair.error.message}</p>}
        <p className="footnote">
          Detail, tonal distribution and clipping describe the preview.
          Aesthetic output and relative ranking are model/heuristic assessments.
          Embedding similarity does not establish artistic originality,
          storytelling or competition eligibility. RAW recovery remains unknown.
        </p>
      </div>
    </Modal>
  );
}
