# NV05 prospective developer annotation adjudication

Recorded on 14 October 2026 before any `structured-1.13` model call. This is a separate AI-developer semantic review, not independent human adjudication. It changes no frozen input, label, manifest, scorer, historical prediction or historical score.

The known regression sentence is: “In fictional brass weavers, higher spool tension correlated with grooved bobbins.” Correlation is symmetric; this sentence does not uniquely assign analyst exposure/outcome roles. The frozen label accepts only intervention `grooved bobbins` and measured outcome `higher spool tension`. The reverse complete pair expresses the same stated association. Previous model results exposed this annotation problem; this partition is already regression data and cannot support an unseen-performance claim.

For a separately labelled sensitivity analysis of subsequent known regression runs, accept either complete pair, with exact input grounding required for both. All other fields, cases, denominators and engineering thresholds remain unchanged. Accepting individual phrases independently is prohibited: duplicating the same phrase in both slots does not pass. Unknown or ambiguous role slots are not scored as successful extraction under this sensitivity analysis. This policy is frozen before the next run and cannot be extended after observing its result.

Every subsequent run must retain its unmodified strict `score.json`; the separate `adjudicated-score.json` must identify this review and report whether this is the only adjusted case. No production behavior or case-specific extraction branch is introduced. The untouched final and challenge partitions retain their original scoring rules.

The correction does not establish effect direction, causation, clinical validity, or useful treatment guidance. A pass only on this adjusted known regression is not fresh qualification.
