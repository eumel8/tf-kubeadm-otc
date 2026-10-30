output "kubeadm-api" {
  value = var.create_dns ? "https://${var.kubeadm_host}.${var.kubeadm_domain}" : opentelekomcloud_networking_floatingip_v2.kubeadm.address
}

output "kubeadm-info" {
  value = ["Welcome to Kubeadm at OTC! It will take up to 5 minutes before your cluster is ready and accessable",
           "To get kubeadm config from lighttpd server:",
           "curl -o kubeadm.config http://${opentelekomcloud_networking_floatingip_v2.kubeadm.address}:8085/${random_string.random.id}/kubeadm.config",
           "export KUBECONFIG=$(pwd)/kubeadm.config",
           "To get kubeadm config via scp:",
           "scp ubuntu@${opentelekomcloud_networking_floatingip_v2.kubeadm.address}:/var/www/html/${random_string.random.id}/kubeadm.config .;export KUBECONFIG=./kubeadm.config",
           "To access the server via ssh:",
           "ssh ubuntu@${opentelekomcloud_networking_floatingip_v2.kubeadm.address}",
           "We provided some additional resource via install script on /install-software.sh",
           "To get: curl -o install-software.sh http://${opentelekomcloud_networking_floatingip_v2.kubeadm.address}:8085/${random_string.random.id}/install-software.sh"
           ]
}
