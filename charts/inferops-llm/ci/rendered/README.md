# Committed renders

These two files are the output of `helm template`, byte for byte, with one
normalisation: line endings are stored as `LF`, because this repository is
developed on Windows and a `CRLF` copy would turn every re-render into a
whole-file diff.

They exist so that the properties a rendered manifest has to carry — the six pod
and container security fields, digest-pinned images, `ClusterIP` with no node
port, the isolation and lifecycle labels, no `Namespace` and no
`PersistentVolumeClaim` — are checked on every run of the default lane, on a
machine that has no Helm and no cluster.
[`tests/architecture/test_helm_chart.py`](../../../../tests/architecture/test_helm_chart.py)
reads them.

They are **not** evidence that this chart installs. Nothing here has been
applied to a cluster. A rendered manifest is a file; whether the objects in it
schedule, become ready, and can be removed without residue is answered by
[the lifecycle script](../../../../scripts/environment/helm-lifecycle.sh), which
has never been run because no InferOps API image is published.

The API image digest in both files is a placeholder that resolves to no image,
for the reason [`../real-values.yaml`](../real-values.yaml) states.

## Regenerating

Run both commands from the repository root, then normalise the line endings.
The suite compares its own re-render against these files whenever `helm` is on
`PATH`, so a stale copy is a failing test rather than a quiet divergence.

```sh
for profile in mock real; do
  helm template inferops charts/inferops-llm \
    --namespace inferops-platform \
    --values "charts/inferops-llm/ci/${profile}-values.yaml" \
    | sed 's/\r$//' > "charts/inferops-llm/ci/rendered/${profile}.expected.yaml"
done
```

The release name and the namespace are part of the output, so both have to stay
exactly as they are above.
