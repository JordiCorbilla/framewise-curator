# Make Framewise more selective, then make it more personal

## Control how many photographs it recommends

In **Curate**, choose **Very selective · 5%**, **Selective · 10%**, or **Balanced · 25%**.
The slider supports any percentage from 1 to 100. The automatic budget rounds up to a whole frame.
Manual Keep, Exclude and Review decisions stay protected, so the final count can differ from the budget.
Changing quantity does not teach the model your taste.

For exceptional recommendations, open **Highlights → Ranking controls & quality floors**.
**Use stricter floors** prepares a competition aesthetic floor of 7.5/10, technical floor of 55/100,
Flickr aesthetic floor of 7.5/10, 95th aesthetic percentile and a maximum of six automatic standouts.
Review the values and choose **Save & rerank Highlights**. It disables Exactly three; fewer than three
finalists is a valid result. These are adjustable heuristics, not validated artistic thresholds.

## Teach the local preference profile

1. Open photographs in the lightbox. Under **My taste**, choose **Like** or **Dislike**.
2. Label at least **10 distinct likes and 10 distinct dislikes**. Include varied examples across trips.
   Feedback is global to this local workspace. Keep/Exclude and stars never become taste labels implicitly.
3. Open **Settings → Your taste, learned locally → Train local profile**.
4. Inspect training/held-out counts and balanced accuracy. **Apply personal ranking** is available only
   when held-out balanced accuracy reaches 60%. Applying is an explicit choice; training starts paused.
5. Review the new shortlist. **Pause personal ranking** returns to generic ranking without losing labels.
   Changing a label pauses and removes the old learned vector; train again when ready.

Labels need current cached embeddings from a matching encoder. A saved label without an embedding is
not counted as usable training data. Complete **Fill cached analysis** in Highlights if embeddings are missing.
Burst groups, verified RAW/JPEG pairs and near-identical perceptual hashes count together. Groups with
contradictory feedback are excluded. The same capture cannot contribute one version to training and another
to the internal holdout. Profile counts use one compatible encoder, selected for balanced class coverage.

## What the learner actually does

`taste-centroid-v1` uses the existing normalised 512-dimensional CLIP vectors. It reserves 25% of each
class, rounded up, in a deterministic group holdout. It fits the difference between the liked and disliked
training centroids, with a midpoint intercept and a training-only margin scale. Held-out examples are not
refitted into the published profile. A sigmoid maps margins to a 0–100 **affinity display scale**; it is
not a calibrated probability. No neural encoder or LAION predictor weights are changed.

When enabled, matching images receive **70% generic score + 30% taste affinity** in ordinary curation
and in the independent Highlights ranker. Missing/mismatched embeddings retain their generic score.
Highlights quality floors, duplicate suppression and manual locks still apply. Evidence and CSV exports
record the affinity and profile version. Training inputs, held-out IDs, encoder, dataset fingerprint,
algorithm, fitted vector and measurements stay in the local SQLite database.

The 60% gate is a basic internal safeguard, not evidence of reliable future performance. At the minimum
dataset size, only six groups are held out. Similar images and a small sample can make results optimistic.
Use separate historical trips, never used for taste training, for the [offline agreement workflow](highlights.md#offline-preference-evaluation).
The app has no measured personal-quality result until you provide real labels.

## Rename, remove and forget

**Library → Rename** changes the display title; the source folder is unchanged.

**Library → Remove** asks you to type the exact title, then permanently removes the collection’s app
records, decisions, taste labels and cached previews. Cancel a running scan and wait for it to stop first.
The source folder and original photographs are never deleted. Existing CSV downloads and independent
backups are outside this removal operation. Re-adding a removed folder creates a fresh collection.

Removing a collection resets the global learned vector, which may include its contributions. Labels in
other collections remain available for retraining. **Settings → Forget my taste data** clears all explicit
taste labels and the profile across all collections; selections and star ratings remain. This removes active
app records, not a forensic secure erase of SQLite pages, filesystem history or your backups.

All learning is local. No image uploads, training service or additional large model download is involved.
