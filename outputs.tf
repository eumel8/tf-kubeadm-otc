output "public_ip" {
  value = opentelekomcloud_networking_floatingip_v2.ncm.address
}

output "ssh_command" {
  value = "ssh ubuntu@${opentelekomcloud_networking_floatingip_v2.ncm.address}"
}

output "webui_url" {
  value = "http://${opentelekomcloud_networking_floatingip_v2.ncm.address}:8080/"
}

output "ncm_info" {
  value = [
    "Installation: sudo cloud-init status --wait (first boot includes a driver reboot)",
    "Bootstrap log: sudo less /var/log/ncm-bootstrap.log",
    "GPU: nvidia-smi",
    "Job status: sudo systemctl status ncm-tinystories",
    "Job logs: sudo journalctl -u ncm-tinystories -f",
    "Run again: sudo systemctl restart ncm-tinystories",
    "Results: /opt/ncm/results/<UTC timestamp>/ (stories.jsonl, evaluation.log, shard logs)",
  ]
}
