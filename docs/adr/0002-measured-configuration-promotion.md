# ADR 0002: Promote measured configuration, retain evidence

Status: accepted. Date: 2026-10-20.

The first improvement loop changes bounded rule configuration rather than rewriting
arbitrary agent source or downloading a model. The default candidate ranks targets by
collision-free A* path length; baseline ranks by straight-line distance. This can reduce
detours around obstacles, but any gain must be measured on the unchanged seed suite.

Reports carry fixed conditions, a harness hash, environment, treatment and latency
distributions. Proposals retain immutable report bytes and verify hashes before
promotion. A SQLite transaction serializes competing approval clients. Deployment is
explicit approval of a pending, eligible proposal. Future reference jobs read the active
configuration. Existing jobs and other backends retain their selected treatment.

The gate rejects failed outcomes, success/perception regression, step regression,
P95 latency regression over 25%, and no measured improvement. The tolerance is explicit,
not a statistical significance claim. Five seeds demonstrate a fixture improvement,
not generalization to other games. Monitoring accepts the same conditions and can roll
back to the previous configuration. Generic self-editing code/model deployment remains
unimplemented until separately validated.
