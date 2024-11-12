# tf-kubeadm-otc

Install Kubeadm OTC with Tofu

## Pre-requirements

* install [tofu](https://opentofu.org/docs/intro/install/)
* have a OTC tenant and AK/SK credentials


## Deployment


* Create a `terraform.tfvars` file in the main folder

mandatory flags:

```
# app
environment    = <environment name>  # e.g. "kubeadm-test"
kubeadm_host   = <hostname>          # e.g. "kubeadm"
kubeadm_domain = <fqdn>              # e.g. "example.com"
create_dns     = "true"
flavor_id      = "c3.xlarge.2"
# secret
access_key     = <otc access key>
secret_key     = <otc secret key>
domain_name    = <otc user domain>"
public_key     = <public ssh key vor ECS>
```

additional features (optional):

```
create_dns     = <create dns zone/zonerecord in otc for rancher_host/rancher_dom> # e.g. "true"
admin_email    = <admin email address for DNS/LetsEncrypt> # e.g. "nobody@telekom.de"
```

```
tofu init
tofu plan
tofu apply -auto-approve
```

## kubeadm installation

There are various steps to prepare Kubernetes installation done by [cloud-init](files/kubeadm)

* set kernel parameters
* set container engine
* install kubeadm, kubelet, kubectl
* create the cluster (single node)
* untain the control-node and make this as worker
* install tooling like helm
* install local-storage provisioner
* generate kube config credential file to download via ssh

## OS-Upgrade (i.e. Kernel/new image) can be done in the following way:

```
tofu taint opentelekomcloud_compute_instance_v2.k3s-server-1
tofu plan
```

This will replace server with a new instance.

Note: this will also upgrade/downgrade the defined version of Rancher and Cert-Manager


## Shutdown-Mode

Since Version 1.23.6 Terraform Open Telekom Cloud can handle ECS instance power state.

Shutoff:

```
tofu apply -auto-approve --var power_state=shutoff
```

Active:

```
tofu apply -auto-approve --var power_state=active
```

## Retirement:

```
tofu destroy
```

## Credits:

Frank Kloeker <f.kloeker@telekom.de>

Life is for sharing. If you have an issue with the code or want to improve it,
feel free to open an issue or an pull request.
