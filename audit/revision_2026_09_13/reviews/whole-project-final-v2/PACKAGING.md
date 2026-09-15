# Provenance of the final report

The numerical collector finished in job 8466129 and saved metrics after all data checks; a later text-rendering step failed on the intentionally unavailable soft-selection oracle. This finalizing Slurm job verifies each copied evidence file against its original, records a separate validation manifest beside that completed checkpoint, and renders the report again. The earlier failure is preserved in inputs/collector-log.txt. No experiment is rerun or altered to repair presentation. The new independent Lean blocker diagnosis has its own manifest.

All final package outputs have fixed hashes. Slurm stdout is outside the final output folder. Upstream recursive verification was performed by the numerical collector before the checkpoint; the finalizer verifies copied-file identity and the additional blocker manifest. External weights and the entire activation dataset remain on Zhores.
