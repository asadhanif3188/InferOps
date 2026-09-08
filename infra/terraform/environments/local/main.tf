# The whole of the local prerequisite layer is one module call. There is nothing
# else here, and that is the point: if a second resource ever appears in this
# file, the question to ask first is which of Terraform and Helm owns it.
module "platform_prerequisites" {
  source = "../../modules/platform-prerequisites"

  namespace              = var.namespace
  model_cache_claim_name = var.model_cache_claim_name
  model_cache_size       = var.model_cache_size
  storage_class_name     = var.storage_class_name
}
