variable "environment" {
  type    = string
  default = "ncm-tinystories"
}

variable "auth_url" {
  type    = string
  default = "https://iam.eu-de.otc.t-systems.com/v3"
}

variable "region" {
  type    = string
  default = "eu-de"
}

variable "tenant_name" {
  type    = string
  default = "eu-de"
}

variable "domain_name" {
  description = "OTC account domain."
  type        = string
  default     = null
}

variable "access_key" {
  type      = string
  sensitive = true
  default   = null
}

variable "secret_key" {
  type      = string
  sensitive = true
  default   = null
}

variable "vpc_cidr" {
  type    = string
  default = "10.1.0.0/24"
}

variable "subnet_cidr" {
  type    = string
  default = "10.1.0.0/24"
}

variable "subnet_gateway_ip" {
  type    = string
  default = "10.1.0.1"
}

variable "subnet_primary_dns" {
  type    = string
  default = "100.125.4.25"
}

variable "subnet_secondary_dns" {
  type    = string
  default = "100.125.129.199"
}

variable "availability_zone1" {
  description = "AZ with capacity for the selected GPU flavor."
  type        = string
  default     = "eu-de-01"
}

variable "image_name" {
  description = "Ubuntu 22.04 x86_64 image compatible with the selected GPU flavor."
  type        = string
  default     = "Standard_Ubuntu_22.04_latest"
}

variable "flavor_id" {
  description = "OTC GPU passthrough flavor, e.g. p3.2xlarge.8 (A100). Check tenant quota and AZ availability."
  type        = string
  default     = "p3.2xlarge.8"

  validation {
    condition     = can(regex("^(p2s|p2v|p3|p5s|p5e|pi2)\\.", var.flavor_id))
    error_message = "Select a supported NVIDIA compute/inference GPU flavor (p2s, p2v, p3, p5s, p5e or pi2)."
  }
}

variable "public_key" {
  description = "SSH public key for the Ubuntu user."
  type        = string

  validation {
    condition     = can(regex("^(ssh-(ed25519|rsa)|ecdsa-sha2-[^ ]+) ", var.public_key))
    error_message = "Set public_key to a valid SSH public key."
  }
}

variable "ssh_allowed_cidr" {
  description = "IPv4 network allowed to connect via SSH, e.g. your public IP/32."
  type        = string
  default     = "0.0.0.0/0"

  validation {
    condition     = can(cidrnetmask(var.ssh_allowed_cidr))
    error_message = "ssh_allowed_cidr must be an IPv4 CIDR."
  }
}

variable "webui_allowed_cidr" {
  description = "IPv4 CIDR permitted to use the public NCM WebUI (0.0.0.0/0 allows the whole internet)."
  type        = string
  default     = "0.0.0.0/0"

  validation {
    condition     = can(cidrnetmask(var.webui_allowed_cidr))
    error_message = "webui_allowed_cidr must be an IPv4 CIDR."
  }
}

variable "root_volume_size" {
  description = "Root SSD in GiB, including Python/CUDA libraries, checkpoints and Hugging Face cache."
  type        = number
  default     = 100

  validation {
    condition     = var.root_volume_size >= 60 && floor(var.root_volume_size) == var.root_volume_size
    error_message = "Use at least 60 GiB and an integer size."
  }
}

variable "power_state" {
  type    = string
  default = "active"

  validation {
    condition     = contains(["active", "shutoff"], var.power_state)
    error_message = "power_state must be active or shutoff."
  }
}

variable "nvidia_driver_package" {
  description = "Ubuntu proprietary NVIDIA server driver package; select a branch supporting your GPU."
  type        = string
  default     = "nvidia-driver-570-server"

  validation {
    condition     = can(regex("^nvidia-driver-[0-9]+-server$", var.nvidia_driver_package))
    error_message = "Use a package name such as nvidia-driver-570-server."
  }
}

variable "ncm_revision" {
  description = "Pinned HazyResearch/ncm Git commit."
  type        = string
  default     = "c70274273f489abc73832b2b98584a8483b6b203"

  validation {
    condition     = can(regex("^[0-9a-f]{40}$", var.ncm_revision))
    error_message = "ncm_revision must be a full Git commit SHA."
  }
}

variable "checkpoint_revision" {
  description = "Pinned hazyresearch/ncm-checkpoints Hugging Face revision."
  type        = string
  default     = "d342ce8aaea58830eef3b8ad473664673e41f692"

  validation {
    condition     = can(regex("^[0-9a-f]{40}$", var.checkpoint_revision))
    error_message = "checkpoint_revision must be a full commit SHA."
  }
}

variable "auto_start" {
  description = "Start TinyStories automatically after installation and driver reboot."
  type        = bool
  default     = true
}

variable "eval_samples" {
  description = "Number of generated stories per seed (upstream uses five seeds)."
  type        = number
  default     = 16

  validation {
    condition     = var.eval_samples > 0 && floor(var.eval_samples) == var.eval_samples
    error_message = "eval_samples must be a positive integer."
  }
}

variable "eval_batch_size" {
  description = "Generation batch size; start small and increase according to available VRAM."
  type        = number
  default     = 4

  validation {
    condition     = var.eval_batch_size > 0 && floor(var.eval_batch_size) == var.eval_batch_size
    error_message = "eval_batch_size must be a positive integer."
  }
}
