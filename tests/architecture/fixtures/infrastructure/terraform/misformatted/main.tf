# Refused by `terraform fmt -check`: the two assignments below are not
# aligned. Nothing else about this module is wrong.
terraform {
  required_version = ">= 1.9.0"
}

locals {
  namespace = "inferops-platform"
  release_name   = "inferops"
}
