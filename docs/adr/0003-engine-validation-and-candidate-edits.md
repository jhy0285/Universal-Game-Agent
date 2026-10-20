# ADR 0003: Engine evidence and separate revision candidates

Status: accepted, 2026-10-20.

The CPU pixel arena remains a reproducible perception benchmark. Godot execution is
an explicit backend with separate evidence: import, six engine rules, truth-bridge play,
and optional release export. An export is a build only when a new nonempty executable
exists and no engine errors were reported. Windows cross-export is distinct from runtime
validation. A run nonce prevents old files from being accepted as current evidence.

Editor/export memory is bounded at 1 GiB after measuring about 651 MiB editor RSS;
gameplay keeps a 512 MiB budget and a five-second action acknowledgment deadline.
Python and engine resource samples are reported separately. All limits remain enforced.

Project edits use hash-checked text plans on a new bounded copy. Failed candidates and
diagnostics remain reviewable; neither a successful test nor a repair promotes the candidate
to the original project. Automatic repair currently handles one confirmed template defect.
General generated code repair and executing untrusted project code are outside this contract.

Long-run evidence uses actual elapsed time, run identity and source fingerprints. Bounded
accumulators avoid retaining one memory sample per episode. Milestones record only elapsed
thresholds already reached; a live heartbeat is never substituted for a completed summary.
