
########### 
# VPC part
########### 
resource "opentelekomcloud_vpc_v1" "vpc" {
  name   = var.environment
  cidr   = var.vpc_cidr
}

resource "opentelekomcloud_vpc_subnet_v1" "subnet" {
  name          = var.environment
  vpc_id        = opentelekomcloud_vpc_v1.vpc.id
  cidr          = var.subnet_cidr
  gateway_ip    = var.subnet_gateway_ip
  primary_dns   = var.subnet_primary_dns
  secondary_dns = var.subnet_secondary_dns
}

########### 
# DNS part 
########### 
resource "opentelekomcloud_dns_zone_v2" "dns" {
  count       = var.create_dns ? 1 : 0
  name        = "${var.kubeadm_domain}."
  email       = var.admin_email
  description = "tf managed zone"
  ttl         = 300
  type        = "public"
}

resource "opentelekomcloud_dns_recordset_v2" "public_record" {
  count       = var.create_dns ? 1 : 0
  zone_id     = opentelekomcloud_dns_zone_v2.dns[0].id
  name        = "${var.kubeadm_host}.${var.kubeadm_domain}."
  description = "tf managed zone"
  type        = "A"
  ttl         = 300
  records     = [ opentelekomcloud_networking_floatingip_v2.kubeadm.address ]
}

########### 
# ECS part
########### 
locals {
  kubeadm = templatefile("${path.module}/files/kubeadm",{
    kubeadm_host = var.kubeadm_host
    kubeadm_domain = var.kubeadm_domain
  })
}

data "opentelekomcloud_images_image_v2" "kubeadm" {
  name        = var.image_name_kubeadm
  most_recent = true
}

# Secgroup part (ECS)
resource "opentelekomcloud_networking_secgroup_v2" "kubeadm" {
  description = "Kubeadm Server"
  name        = "${var.environment}-secgroup"
}
 
resource "opentelekomcloud_networking_secgroup_rule_v2" "sg_kubeadm_all_out" {
  description       = "Kubeadm accept all traffic"
  direction         = "egress"
  ethertype         = "IPv4"
  remote_ip_prefix  = "0.0.0.0/0"
  security_group_id = opentelekomcloud_networking_secgroup_v2.kubeadm.id
}
 

resource "opentelekomcloud_networking_secgroup_rule_v2" "sg_icmp_in" {
  description       = "Kubeadm accept icmp ingress"
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "icmp"
  remote_ip_prefix  = "0.0.0.0/0"
  security_group_id = opentelekomcloud_networking_secgroup_v2.kubeadm.id
}

resource "opentelekomcloud_networking_secgroup_rule_v2" "sg_tcp_22_in" {
  description       = "Kubeadm accept tcp/22 ingress"
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 22
  port_range_max    = 22
  remote_ip_prefix  = "0.0.0.0/0"
  security_group_id = opentelekomcloud_networking_secgroup_v2.kubeadm.id
}

resource "opentelekomcloud_networking_secgroup_rule_v2" "sg_tcp_6443_in" {
  description       = "Kubeadm accept tcp/6443 ingress"
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 6443
  port_range_max    = 6443
  remote_ip_prefix  = "0.0.0.0/0"
  security_group_id = opentelekomcloud_networking_secgroup_v2.kubeadm.id
}

# ssh key part
resource "opentelekomcloud_compute_keypair_v2" "kubeadm" {
  name       = "${var.environment}-key"
  public_key = var.public_key
}

# ECS part (instances)

resource "opentelekomcloud_compute_instance_v2" "kubeadm" {
  name              = "${var.environment}-kubeadm"
  availability_zone = var.availability_zone1
  flavor_id         = var.flavor_id
  key_pair          = opentelekomcloud_compute_keypair_v2.kubeadm.name
  security_groups   = ["${var.environment}-secgroup"]
  user_data         = local.kubeadm
  power_state       = var.power_state
  network {
    uuid = opentelekomcloud_vpc_subnet_v1.subnet.id
  }
  block_device {
    boot_index            = 0
    source_type           = "image"
    destination_type      = "volume"
    uuid                  = data.opentelekomcloud_images_image_v2.kubeadm.id
    delete_on_termination = true
    volume_size           = 30
  }
}

resource "opentelekomcloud_networking_floatingip_v2" "kubeadm" {
  pool  = "admin_external_net"
}

resource "opentelekomcloud_networking_floatingip_associate_v2" "kubeadm" {
  floating_ip = opentelekomcloud_networking_floatingip_v2.kubeadm.address
  port_id     = opentelekomcloud_compute_instance_v2.kubeadm.network.0.port
}
