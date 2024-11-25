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

## Output

After `tofu apply` or `tofu output` show a lot of information to access the cluster:


```bash
Outputs:

kubeadm-api = "https://kubeadm.otc.mcsps.de"
kubeadm-info = [
  "Welcome to Kubeadm at OTC! It will take up to 5 minutes before your cluster is ready and accessable",
  "To get kubeadm config from lighttpd server:",
  "curl -o kubeadm.config http://164.30.35.56:8181/cvivcfat6mol7te0e4jxr5zez0m0ig53/kubeadm.config",
  "export KUBECONFIG=$(pwd)/kubeadm.config",
  "To get kubeadm config via scp:",
  "scp ubuntu@164.30.35.56:/var/www/html/cvivcfat6mol7te0e4jxr5zez0m0ig53/kubeadm.config .;export KUBECONFIG=./kubeadm.config",
  "To access the server via ssh:",
  "ssh ubuntu@164.30.35.56",
  "We provided some additional resource via install script on /install-software.sh",
  "To get: curl -o install-software.sh http://164.30.35.56:8181/cvivcfat6mol7te0e4jxr5zez0m0ig53/install-software.sh",
]

$ scp ubuntu@164.30.35.56:/var/www/html/cvivcfat6mol7te0e4jxr5zez0m0ig53/kubeadm.config .;export KUBECONFIG=./kubeadm.config
$ kubectl get nodes
NAME                   STATUS   ROLES           AGE     VERSION
kubeadm-test-kubeadm   Ready    control-plane   6m19s   v1.28.15
```

## Software

Within cloud-init a file named /install-software.sh will installed. It can be executed to install

- kube-prometheus-stack
- kube-logging
- ingress-nginx
- kube-vip

see hints in the file for further information

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
