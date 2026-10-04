# Git desired state

This directory holds the desired state of InferOps workloads, as generated releases.
A GitOps controller is meant to reconcile a cluster to it. **Nothing reconciles it
yet.**

Every file below this page is generated. Do not edit one by hand.

```text
gitops/
└── environments/
    └── <environment binding>/
        └── workloads/
            └── <workload id>/
                ├── rendered-workload-release.yaml
                └── values.generated.yaml
```

- A release directory is `<destinationPath>/workloads/<workloadId>`. The
  EnvironmentBinding declares the destination path. The WorkloadContract names the
  workload.
- A release directory holds the two generated files and nothing else. A
  hand-written values file does not belong in this tree.
- To change a release, change the WorkloadContract, the EnvironmentBinding, or the
  platform defaults it is rendered from. Then regenerate it, and review the
  generated difference in the same change.
- The desired state changes when a reviewed change is accepted into `main`. No
  second promotion step exists.

```sh
# Verify the whole tree. Writes nothing.
uv run --locked python -m tools.gitops_desired_state --check
# Regenerate one release, after a deliberate change to one of its inputs.
uv run --locked python -m tools.gitops_desired_state --write local-docker-desktop/support-assistant
```

[The desired-state document](../docs/environment/git-desired-state.md) states the
rules, the promotion boundary, and what this tree does not establish.
