terraform {
  required_version = ">= 1.6.0"
  required_providers {
    opentelekomcloud = {
      source  = "opentelekomcloud/opentelekomcloud"
      version = "~> 1.36"
    }
  }
}

provider "opentelekomcloud" {
  region      = var.region
  access_key  = var.access_key
  secret_key  = var.secret_key
  domain_name = var.domain_name
  tenant_name = var.tenant_name
  auth_url    = var.auth_url
}
