# Refused by tflint (terraform_documented_variables) and by nothing else. That
# rule is in the `all` preset and not in `recommended`, which is tflint's
# default, so this fixture is refused only when the committed .tflint.hcl was
# actually applied. It is the control that catches a gate whose configuration
# was silently not read.
terraform {
  required_version = ">= 1.9.0"
}
