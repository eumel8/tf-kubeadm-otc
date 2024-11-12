output "kubeadm-api" {
  value = ["https://${var.kubeadm_host}.${var.kubeadm_domain}",
           "scp ubuntu@${opentelekomcloud_networking_floatingip_v2.kubeadm.address}:/tmp/kubeadm.config .;export KUBECONFIG=./kubeadm.config",
           "ssh ubuntu@${opentelekomcloud_networking_floatingip_v2.kubeadm.address}"]
}
