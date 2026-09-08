# The version floor and the provider pin, stated once and repeated by the
# environment that calls this module.
#
# The provider version is exact rather than a range. Everywhere else in this
# repository a pin is exact -- the node image by digest, the runtime image by
# digest, the model by revision and per-file hash -- because a range resolves to
# whatever was published most recently, and "it worked yesterday" is then a
# statement about the registry rather than about this configuration. The lock
# file beside the environment records the same version and its checksums for
# every platform a contributor is expected to run on.
#
# It is deliberately 2.38.0 and not the 3.x line. Moving a provider across a
# major version changes resource schemas and state representation, and that is a
# decision to take with a plan against a real cluster in front of you. Nothing
# here has ever been applied, so this configuration is in no position to make
# that call; upgrading is a separate, separately-validated change.
terraform {
  required_version = ">= 1.9.0"

  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "2.38.0"
    }
  }
}
