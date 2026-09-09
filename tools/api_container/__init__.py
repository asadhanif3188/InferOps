"""The entrypoint the InferOps API container runs.

One module, one job: read the bind address out of the environment, compose the
application the environment describes, serve it until the orchestrator says stop,
and drain. It is separate from `tools.local_composition` because the two answer
different questions about the same application -- that one runs it on a
contributor's host behind loopback, this one runs it inside a pod behind a
Service -- and a single module that tried to be both would end up with a default
that quietly decided which.
"""
