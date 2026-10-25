# From Framewise to Lightroom Classic

1. Open a collection and inspect **Curate**. Use P/Space to keep, X to exclude, U to reset, 1–5 to rate.
2. Open **Selected**, then **Final selection**. Manual Keep/Reject/Review decisions take precedence.
3. Open **Export** and download `selected_photos.csv`; optionally download `all_photos.csv` as an audit.
4. Open the CSV in a spreadsheet. It lists the exact absolute/relative source paths, filename,
   overall/aesthetic/detail/exposure values, AI recommendation, manual decision, final selected status,
   star rating, group ID and selection rank. Files use UTF-8 BOM and CSV quoting for Unicode/commas.
5. In Lightroom Classic use **File → Import Photos and Video**, select the original NEF folder and
   choose **Add** to leave photographs where they are. Use the shortlist filenames as a reference to
   manually add the chosen frames to a Collection or apply ratings.

**Lightroom Classic does not automatically convert CSV into a Collection.** No Lightroom plugin is
included. Already-catalogued photos do not need another import. If tested XMP integration is added
later, they may require **Metadata → Read Metadata from Files**; reconcile existing Lightroom metadata
first because synchronising external metadata can affect catalogue adjustments.

## XMP status

Sidecar writing is **disabled** in V1. The dry-run endpoint reports existing `.xmp` conflicts; confirmation
always returns 409. No source sidecar is modified. Reliable merging, backups, configurable proposed
star thresholds and Lightroom round-trip tests are deferred together. Existing develop settings,
labels, keywords and adjustments are therefore preserved by leaving them untouched.

Automatic RAW copying is also deferred; Framewise does not copy gigabytes or alter originals.
