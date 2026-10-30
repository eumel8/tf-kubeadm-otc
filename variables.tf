####################
# Environment
####################

variable "environment" {
  default = "kubeadm-test"
}

####################
#   OTC auth config
####################

variable "auth_url" {
  default = "https://iam.eu-de.otc.t-systems.com/v3"
}

variable "region" {
  default = "eu-de"
}

variable "otc_domain" {
  default = "eu-de"
}

variable "tenant_name" {
  default = "eu-de"
}

variable "domain_name" {
  default = ""
}

variable "access_key" {
  default = ""
}

variable "secret_key" {
  default = ""
}

variable "key" {
  default = ""
}

####################
# VPC vars
####################

variable "vpc_cidr" {
  description = "CIDR of the VPC"  
  default     = "10.1.0.0/24"
}

####################
# Subnet vars
####################

variable "subnet_cidr" {
  description = "CIDR of the Subnet"  
  default     = "10.1.0.0/24"
}

variable "subnet_gateway_ip" {
  description = "Default gateway of the Subnet"  
  default     = "10.1.0.1"
}

variable "subnet_primary_dns" {
  description = "Primary DNS server of the Subnet"  
  default     = "100.125.4.25"
}

variable "subnet_secondary_dns" {
  description = "Secondary DNS server of the Subnet"  
  default     = "100.125.129.199"
}

####################
# ECS vars
####################

variable "availability_zone1" {
  description = "Availability Zone 1 (Biere)"
  default     = "eu-de-01"
}

variable "availability_zone2" {
  description = "Availability Zone 2 (Magdeburg)"
  default     = "eu-de-02"
}

variable "availability_zone3" {
  description = "Availability Zone 3 (Biere)"
  default     = "eu-de-03"
}

variable "image_name_kubeadm" {
  description = "Name of the image"
  default     = "Standard_Ubuntu_22.04_latest"
}

variable "flavor_id" {
  description = "ID of Flavor"
  default     = "c3.large.4"
}

variable "public_key" {
  description = "ssh public key to use"
  default     = ""
}

variable "power_state" {
  description = "Power state of ECS instances"
  default     = "active"
}

####################
# DNS vars
####################

variable "create_dns" {
  description = "Create DNS entries"
  type        = bool
  default     = false
}

variable "kubeadm_host" {
  description = "Public host of the kubeadm instance"
  default     = "kubeadm"
}

variable "kubeadm_domain" {
  description = "Public domain of the kubeadm instance"
  default     = "example.com"
}

variable "admin_email" {
  description = "Admin email address for DNS and LetsEncrypt"
  default     = "nobody@example.com"
}

####################
# Kubeadm vars
####################
