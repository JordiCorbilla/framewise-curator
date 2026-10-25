# Measured features and recommendations

Framewise's general profile uses 60% aesthetic, 25% detail and 15% tonal quality. These are configurable
ranking heuristics, not probabilities of publication, competition wins or social engagement.
There is no independent composition, creativity, subject or genre detector.

## Aesthetic model

The installed pair is **OpenAI CLIP ViT-B/32** with QuickGELU and OpenAI preprocessing (224px bicubic
resize/centre crop and OpenAI mean/std), plus **LAION aesthetic predictor V1**,
`sa_0_4_vit_b_32_linear.pth`: 512-dimensional linear head with bias. Image embeddings are L2-normalised
before the head. The raw model output is displayed on its conventional /10 scale; only the aggregate
ranking clamps its scaled value to 0–100. This is a broad aesthetic proxy, not an artistic verdict.

Sources: [LAION predictor](https://github.com/LAION-AI/aesthetic-predictor),
[reference inference](https://github.com/rom1504/embedding-reader/blob/main/examples/aesthetic_inference.py),
[OpenCLIP](https://github.com/mlfoundations/open_clip), [OpenAI CLIP](https://github.com/openai/CLIP).
No source code from the UI inspiration projects is copied.

The consent installer records exact checkpoint URLs, the LAION Git commit, SHA256 digests, embedding
contract and installation timestamp in `models/manifest.json`. OpenAI's published URL SHA256 is checked
at installation; both stored hashes are checked before runtime loading. The OpenAI file is a TorchScript
archive loaded explicitly with `torch.jit.load`, then loaded strictly into the OpenCLIP architecture;
the linear head is loaded with `weights_only=True`. No model name triggers a runtime download.

`uv sync --extra ai` installs optional dependencies; the separate consent command installs weights.
Without either, aesthetic values remain null and the UI says technical-only ranking. Remaining weights
are renormalised, rather than presenting classical measurements as AI output. Each scan records its
model/configuration; missing inference after a model error remains retryable.

## Technical measurements

Measurements use RGB previews downsampled to at most 1024px. Stored raw metrics include Laplacian
variance, contrast-normalised detail, Sobel edge density, luminance mean, standard deviation,
mean RGB and near-black/near-white fractions. Detail is `100*(1-exp(-2*normalised_detail))`, with
normalised detail = Laplacian variance / max(contrast², 0.0025). Low edge density adds an uncertain
focus-risk label. Tonal quality is `clip(100 - 100*highlight_fraction - 35*shadow_fraction, 0, 100)`.
The lower shadow penalty avoids heavily penalising low-key photographs. There is no target brightness
or saturation bonus. Metrics are reproducible but remain scene dependent; they are not validated
focus, editability or exposure judgements. Inspect intentional blur, shallow focus and night scenes.

JPEG clipping does **not** establish unrecoverable RAW clipping. Scores record whether the analysis
source was original raster, embedded JPEG or LibRaw-developed half-size RAW. Preview source dimensions
and the 2560px display limit are disclosed; sensor-level 100% inspection is deferred.

## Similarity and budget

64-bit perceptual hashes, oriented aspect ratio and capture timestamps form conservative groups.
Exact hashes may match without EXIF; other matches require capture times within 12 seconds and hash
distance ≤10, against up to 48 recent group anchors. Distance >6, exposure-compensation changes or
large preview-brightness differences flag a protected, uncertain sequence for review. This is a
bracket/panorama safeguard, not reliable semantic panorama detection.

Groups rank by aggregate score, then filename/ID for deterministic ties. Strongest representatives are
considered before unprotected alternatives to favour diversity. Protected members keep independent
eligibility. Budget selects ceil(ready-photo-count * percentage). The next budget-sized band and
uncertain sequences receive Review; remaining photos receive Low Priority. Nothing is deleted.

Final selection = manual Keep, or automatic Pick when the manual state is Auto. Manual Reject and
Review exclude from the final shortlist. Ratings are independent. Budget/weight updates never change
manual decisions or ratings. AI recommendations can be viewed before overrides on the Selected page.
