import { useState } from "react";
import { Button } from "../../components/ui/button";
import type { HighlightConfig } from "../../types";

export function HighlightSettings({
  config,
  save,
  busy,
}: {
  config: HighlightConfig;
  save: (c: HighlightConfig) => void;
  busy: boolean;
}) {
  const [draft, setDraft] = useState(config);
  const fields = [
    {
      key: "aesthetic_floor",
      label: "Competition aesthetic floor /10",
      min: 0,
      max: 10,
      step: 0.1,
    },
    {
      key: "technical_floor",
      label: "Technical quality floor /100",
      min: 0,
      max: 100,
      step: 1,
    },
    {
      key: "flickr_aesthetic_floor",
      label: "Flickr aesthetic floor /10",
      min: 0,
      max: 10,
      step: 0.1,
    },
    {
      key: "flickr_percentile",
      label: "Flickr aesthetic percentile",
      min: 0,
      max: 100,
      step: 1,
    },
    {
      key: "aesthetic_weight",
      label: "Aesthetic percentile weight",
      min: 0,
      max: 1,
      step: 0.05,
    },
    {
      key: "technical_weight",
      label: "Technical percentile weight",
      min: 0,
      max: 1,
      step: 0.05,
    },
    {
      key: "distinctiveness_weight",
      label: "Visual distance weight",
      min: 0,
      max: 1,
      step: 0.05,
    },
    {
      key: "diversity_penalty",
      label: "Maximum redundancy penalty",
      min: 0,
      max: 25,
      step: 1,
    },
  ] as const;
  return (
    <details className="highlight-settings">
      <summary>Ranking controls & quality floors</summary>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          save(draft);
        }}
      >
        <p className="footnote">
          Within-collection percentiles rank measured signals; absolute floors
          prevent a weak collection from automatically producing exceptional
          recommendations. Technical quality is one combined proxy, avoiding
          repeated votes for correlated metrics. Weights are normalised over
          available signals.
        </p>
        <div className="form-actions">
          <Button
            type="button"
            variant="outline"
            disabled={busy}
            onClick={() =>
              setDraft({
                ...draft,
                aesthetic_floor: 7.5,
                technical_floor: 55,
                flickr_aesthetic_floor: 7.5,
                flickr_percentile: 95,
                flickr_max: 6,
                force_three: false,
              })
            }
          >
            Use stricter floors
          </Button>
          <span className="footnote">
            Review the values below, then Save. Fewer than three finalists is
            allowed.
          </span>
        </div>
        <div className="highlight-config-grid">
          {fields.map((f) => (
            <label key={f.key}>
              {f.label}
              <input
                type="number"
                required
                min={f.min}
                max={f.max}
                step={f.step}
                value={draft[f.key]}
                onChange={(e) =>
                  setDraft({ ...draft, [f.key]: Number(e.target.value) })
                }
              />
            </label>
          ))}
          <label>
            Maximum automatic Flickr standouts
            <input
              type="number"
              aria-label="Maximum automatic Flickr standouts"
              min={1}
              max={5000}
              placeholder="No limit"
              value={draft.flickr_max ?? ""}
              onChange={(e) =>
                setDraft({
                  ...draft,
                  flickr_max:
                    e.target.value === "" ? null : Number(e.target.value),
                })
              }
            />
          </label>
        </div>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={draft.force_three}
            onChange={(e) =>
              setDraft({ ...draft, force_three: e.target.checked })
            }
          />
          Exactly three when possible — allow below-floor or related frames if
          needed
        </label>
        <p className="footnote">
          The override respects explicit rejections and cannot create missing
          images. Manual choices survive reranking. Theme-based judging is
          deferred; embeddings do not establish category eligibility.
        </p>
        <Button
          variant="outline"
          type="submit"
          disabled={
            busy || draft.aesthetic_weight + draft.technical_weight <= 0
          }
        >
          Save & rerank Highlights
        </Button>
      </form>
    </details>
  );
}
