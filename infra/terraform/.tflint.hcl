# tflint's configuration for the Terraform prerequisite layer.
#
# The `all` preset of the bundled Terraform ruleset rather than `recommended`,
# which is tflint's default. `all` adds documentation, naming, and
# standard-module-structure rules, and this configuration already satisfies
# every one of them, so the stricter preset costs nothing and keeps a later
# change from lowering the bar by accident.
#
# The bundled ruleset is used deliberately. It ships inside the pinned tflint
# binary, so no plugin is downloaded and `tflint --init` is never needed; a
# `source` and `version` here would make the gate fetch a plugin over the
# network on every run.
#
# Pass this file by absolute path. Measured on tflint 0.64.0: under
# `--recursive`, a `.tflint.hcl` that is only present in the `--chdir`
# directory is not applied to the modules below it, and the lint passes with
# tflint's defaults instead. The fixture
# tests/architecture/fixtures/infrastructure/terraform/lint-undocumented-variable
# fails only when this file is read, which is what shows that it was.

plugin "terraform" {
  enabled = true
  preset  = "all"
}
