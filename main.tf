resource "opentelekomcloud_vpc_v1" "vpc" {
  name = var.environment
  cidr = var.vpc_cidr
}

resource "opentelekomcloud_vpc_subnet_v1" "subnet" {
  name          = var.environment
  vpc_id        = opentelekomcloud_vpc_v1.vpc.id
  cidr          = var.subnet_cidr
  gateway_ip    = var.subnet_gateway_ip
  primary_dns   = var.subnet_primary_dns
  secondary_dns = var.subnet_secondary_dns
}

data "opentelekomcloud_images_image_v2" "ncm" {
  name        = var.image_name
  most_recent = true
}

locals {
  cloud_init = "#cloud-config\n${yamlencode({
    write_files = [
      {
        path        = "/usr/local/sbin/ncm-bootstrap"
        permissions = "0755"
        content = templatefile("${path.module}/files/ncm-bootstrap.sh.tftpl", {
          ncm_revision          = var.ncm_revision
          checkpoint_revision   = var.checkpoint_revision
          nvidia_driver_package = var.nvidia_driver_package
          auto_start            = var.auto_start
        })
      },
      {
        path        = "/usr/local/bin/ncm-tinystories"
        permissions = "0755"
        content = templatefile("${path.module}/files/ncm-tinystories.sh.tftpl", {
          eval_samples    = var.eval_samples
          eval_batch_size = var.eval_batch_size
        })
      },
      {
        path        = "/etc/systemd/system/ncm-tinystories.service"
        permissions = "0644"
        content     = file("${path.module}/files/ncm-tinystories.service")
      },
      {
        path        = "/opt/ncm/deutsche-geschichte.py"
        permissions = "0755"
        content     = file("${path.module}/files/deutsche-geschichte.py")
      },
      {
        path        = "/opt/ncm/ncm-webui.py"
        permissions = "0755"
        content     = file("${path.module}/files/ncm-webui.py")
      },
      {
        path        = "/etc/systemd/system/ncm-webui.service"
        permissions = "0644"
        content     = file("${path.module}/files/ncm-webui.service")
      }
    ]
    runcmd = [["/usr/local/sbin/ncm-bootstrap"]]
  })}"
}

resource "opentelekomcloud_networking_secgroup_v2" "ncm" {
  name        = "${var.environment}-secgroup"
  description = "NCM GPU server"
}

resource "opentelekomcloud_networking_secgroup_rule_v2" "egress" {
  description       = "NCM outbound downloads"
  direction         = "egress"
  ethertype         = "IPv4"
  remote_ip_prefix  = "0.0.0.0/0"
  security_group_id = opentelekomcloud_networking_secgroup_v2.ncm.id
}

resource "opentelekomcloud_networking_secgroup_rule_v2" "sg_tcp_22_in" {
  description       = "NCM SSH access"
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 22
  port_range_max    = 22
  remote_ip_prefix  = var.ssh_allowed_cidr
  security_group_id = opentelekomcloud_networking_secgroup_v2.ncm.id
}

resource "opentelekomcloud_networking_secgroup_rule_v2" "sg_tcp_8080_in" {
  description       = "NCM WebUI access"
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 8080
  port_range_max    = 8080
  remote_ip_prefix  = var.webui_allowed_cidr
  security_group_id = opentelekomcloud_networking_secgroup_v2.ncm.id
}

resource "opentelekomcloud_compute_keypair_v2" "ncm" {
  name       = "${var.environment}-key"
  public_key = var.public_key
}

resource "opentelekomcloud_compute_instance_v2" "ncm" {
  name              = "${var.environment}-ncm"
  availability_zone = var.availability_zone1
  flavor_id         = var.flavor_id
  key_pair          = opentelekomcloud_compute_keypair_v2.ncm.name
  security_groups   = [opentelekomcloud_networking_secgroup_v2.ncm.name]
  user_data         = local.cloud_init
  power_state       = var.power_state

  network {
    uuid = opentelekomcloud_vpc_subnet_v1.subnet.id
  }

  block_device {
    boot_index            = 0
    source_type           = "image"
    destination_type      = "volume"
    uuid                  = data.opentelekomcloud_images_image_v2.ncm.id
    delete_on_termination = true
    volume_size           = var.root_volume_size
    volume_type           = "SSD"
  }
}

resource "opentelekomcloud_networking_floatingip_v2" "ncm" {
  pool = "admin_external_net"
}

resource "opentelekomcloud_networking_floatingip_associate_v2" "ncm" {
  floating_ip = opentelekomcloud_networking_floatingip_v2.ncm.address
  port_id     = opentelekomcloud_compute_instance_v2.ncm.network[0].port
}
