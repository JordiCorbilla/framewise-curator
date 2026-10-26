# Highlights: portfolio standouts and General Best 3

Highlights reuses the installed local CLIP/LAION model, technical metrics and similarity groups.
No additional models, services, uploads or downloads are required.

## Three independent decisions

- **Lightroom Picks**: the ordinary editing shortlist, preserving existing Keep/Reject/Review decisions.
- **Flickr Standouts**: a selective subset of final Lightroom Picks. Manual addition offers **Standout +
  keep** when editing inclusion is also needed. Later Lightroom exclusion makes the standout inactive,
  while retaining its independent feedback.
- **Competition Top 3**: a separate General Best 3 ranking. Lightroom exclusion does not implicitly
  reject a competition candidate; its own Exclude/Demote controls do that.

In **Highlights → Competition Top 3**, inspect #1 Best Shot, #2 Runner-Up and #3 Third Pick. Each has
measured evidence, limitations and a separate relative rank score. The full-screen lightbox retains
technical metrics and related frames. Choose Compare on two frames for side-by-side previews and
concrete model outputs, detail, tonal/clipping features, hash distance and cached cosine similarity.

**Promote to #1** swaps displayed finalists. **Replace #N** locks a photograph into that slot, moves
the displaced finalist to Alternatives and preserves other displayed finalists. **Demote** keeps an
alternative; **Exclude** removes competition eligibility. **Use auto** releases that photo's manual
choice. Reranking does not silently release other locks. Include a frame / Add manually searches all
analysed photographs, 24 per page. Alternatives previews show the next 24; Browse all opens the full
paginated Gallery filter. Flickr Standouts are score-sorted and paginated at 48 per page.

## Explainable ranking

The ordinary editing score does not determine Highlights order. Initial configurable feature weights:

1. **65% aesthetic percentile**, from the installed model's raw output.
2. **20% technical percentile**, using one proxy: 0.65 × detail + 0.35 × tonal quality. Correlated detail,
   contrast, focus-risk and exposure measurements are not counted as independent quality votes.
3. **15% visual-distinctiveness percentile**, from mean cosine distance to the five nearest available
   reference frames outside the similarity group. This measures visual redundancy, not originality.

Percentiles use deterministic midranks for ties; a singleton receives 100. Absolute floors apply before
automatic exceptional recommendations: competition aesthetic ≥6.5 and technical ≥35. Flickr additionally
requires aesthetic ≥7, aesthetic percentile ≥90, Lightroom inclusion and a maximum of 12 automatic
recommendations. High relative rank in a weak collection alone cannot clear the floors. Manual additions
can bypass thresholds/caps and are visibly identified as manual.

Missing signals are omitted and weights renormalised. Without aesthetic output, there are no automatic
exceptional recommendations. Manual inclusion / Exactly three can still expose available frames, with
the missing evidence stated. These heuristics are not calibrated predictions of Flickr engagement,
publication acceptance or competition wins, and do not independently measure composition or storytelling.

Similarity representatives use Highlights scores. Conservative groups and very close oriented hashes
suppress repeated captures; protected groups do not blanket-disqualify distinct compositions. Five hash
bands with bounded buckets avoid whole-library pairwise duplicate searches. Distinctiveness uses at
most 512 deterministic reference embeddings in 128-row blocks, rather than a large N×N matrix.

Greedy finalist reranking applies a soft visual-redundancy penalty, initially up to 8 points when cosine
similarity exceeds 0.85. There are no inferred scene labels or landmark quotas. Distinct compositions of
the same subject remain eligible. Scores, group ranks and alternatives remain inspectable. General Best 3
is implemented; unimplemented theme-based modes are explicitly rejected by the API.

**Exactly three** is an explicit Ranking controls override. It may use below-floor or related frames,
respects explicit rejections and cannot invent absent photos. Automatic fields used in evaluation remain
separate from the manually corrected/forced final selection.

## Cache, source versions and persistence

Scans cache normalised 512-dimensional float32 embeddings with model identity, source fingerprint and
input provenance. Complete cached analysis backfills existing collections from 2560px display JPEGs,
without changing earlier aesthetic values or manual decisions. Missing embeddings are disclosed and their
weight omitted until available. CPU inference loads only previously approved local weights.

RAW embedded previews and edited JPEGs can coexist in a recursive collection. Editing influences model
output; an edited-JPEG score is not an untouched RAW assessment. A registered NEF is associated only
when filename stem, exact capture second and camera model match **uniquely**. Ambiguous or incomplete
metadata produces no association. Linked RAW/JPEG versions cannot occupy two automatic finalist slots
for the same capture, even when editing changes their perceptual hashes. Originals remain read-only.

Additive SQLite tables hold embeddings, RAW associations, rankings, category decisions, finalist slots,
configuration/version and append-only before/after feedback. Existing photo/metric/Lightroom-decision
records are retained. Exceptional ranking waits until scanning finishes; interrupted/cancelled scans
show an explicit waiting state. A separate opt-in local preference learner now uses explicit My taste
labels; category corrections remain potential feedback records rather than implicit training labels.
See [personal preference controls](preferences.md) for the training gate, limits and reset behaviour.

## Lightroom exports

New CSVs: `lightroom_picks.csv`, `flickr_standouts.csv`, `competition_top3.csv` and
`competition_alternatives.csv`. They include original paths, categories, relative scores/ranks, manual
overrides/origins, model/configuration versions, strengths and uncertainties.

Verified JPEG/NEF pairs hand off the original NEF. `analysed_path`, `analysed_filename`,
`analysis_provenance` and `embedding_provenance` retain the real analysis inputs. Unpaired rasters keep
their true original path; no RAW path is invented. Each row remains a recommendation, so a RAW path may
repeat if multiple versions were manually included. `all_photos.csv` preserves actual per-image source
paths, plus independent automatic and corrected recommendations for offline evaluation.

CSV does not automatically create a Lightroom Collection. XMP ratings/keywords remain disabled with
the existing sidecar exporter. No develop settings, labels or other XMP metadata are overwritten.
No Flickr uploads or competition submissions are performed.

## Offline preference evaluation

Export all_photos.csv from a historical trip and create blank labels:

```powershell
.\backend\.venv\Scripts\python.exe .\scripts\evaluate_highlights.py template `
  --predictions .local\highlights\all_photos.csv --output .local\highlights\favourites.csv
```

Explicitly fill **every** Flickr/competition favourite cell with true/false after reviewing the images.
Paths distinguish RAW and edited versions. Keep evaluation trips in the `heldout` split; do not tune
weights on them. Folder names and editing history are not treated as favourite labels.

```powershell
.\backend\.venv\Scripts\python.exe .\scripts\evaluate_highlights.py evaluate `
  --predictions .local\highlights\all_photos.csv --labels .local\highlights\favourites.csv `
  --split heldout --output .local\highlights\agreement.json
```

The evaluator reports Flickr precision/recall/F1 and competition overlap, precision/recall and binary
nDCG at up to three. Precision divides by actually recommended frames; undefined metrics are null.
Incomplete labels, universe mismatches, duplicate paths and invalid ranks are rejected. It uses
**automatic** fields rather than human-corrected finalists, avoiding misleading agreement after manual
replacement. Output records source hashes and model/configuration provenance. No photos, inference,
network or training are required. Evaluate each collection separately and compare held-out historical
reports before promoting ranking changes. No artistic-quality validation is claimed without these labels.
