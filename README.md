# GPU story lab on an Open Telekom Cloud ECS

OpenTofu provisions an [Open Telekom Cloud](https://open-telekom-cloud.com/) (OTC)
GPU-backed Elastic Cloud Server (ECS). Its browser start page creates **German
stories from a freely editable prompt** using
[Qwen2.5-1.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct).
The separate `/ncm` page runs the pretrained **TinyStories** checkpoint from
[HazyResearch/Next-Concept Modeling (NCM)](https://github.com/HazyResearch/ncm).
NCM generates text from coarse to fine; its published TinyStories evaluation
generates *unconditional English stories*. Qwen is **not** an NCM model or
an NCM fine-tune.

## Architecture and bootstrap

OpenTofu creates a VPC, subnet, SSH-restricted security group, keypair, floating
IP and GPU ECS. The defaults are Ubuntu 22.04, a `p3.2xlarge.8` (one NVIDIA A100),
and a 100 GiB SSD. The WebUI binds to `0.0.0.0:8080` and the security group
allows public HTTP access by default (lab setup). Select a GPU flavor and availability zone with available
capacity in your OTC tenant.

Cloud-init installs the NVIDIA server driver, a Python virtual environment with
CUDA-enabled PyTorch, and the dependencies for NCM. It clones the pinned
[NCM repository](https://github.com/HazyResearch/ncm) and downloads only the
TinyStories checkpoint files (generator, tokenizer, config and BPE files) from
the [NCM checkpoint collection](https://huggingface.co/hazyresearch/ncm-checkpoints).
All project-side runtime files are embedded by OpenTofu in cloud-init `write_files`:

| Source in this repository | Path on the ECS | Purpose |
| --- | --- | --- |
| `files/ncm-bootstrap.sh.tftpl` | `/usr/local/sbin/ncm-bootstrap` | Driver, Python, NCM and checkpoint installation |
| `files/ncm-tinystories.sh.tftpl` | `/usr/local/bin/ncm-tinystories` | CUDA check, NCM evaluation and JSONL export |
| `files/ncm-tinystories.service` | `/etc/systemd/system/ncm-tinystories.service` | Automatic systemd job |
| `files/deutsche-geschichte.py` | `/opt/ncm/deutsche-geschichte.py` | German prompt-based CLI/TUI |
| `files/ncm-webui.py` | `/opt/ncm/ncm-webui.py` | German story start page and optional NCM evaluation page |
| `files/ncm-webui.service` | `/etc/systemd/system/ncm-webui.service` | Always-on WebUI service |

The project files are therefore installed on a **fresh** ECS without manual
copying. The upstream NCM source and model weights are fetched from their
respective projects during bootstrap. The ECS reboots once after installation
to load the NVIDIA driver; the NCM job then starts automatically by default.
PyTorch provides the CUDA runtime, so the CUDA compiler toolkit is not needed.

> **Existing ECS:** Changes to cloud-init `user_data` can cause OpenTofu to
> replace the ECS and delete its root disk. If you already deployed this repo
> and only want the updated WebUI, copy the changed files to the running server
> instead of applying an ECS replacement. See the manual update below.

## Prerequisites

- [OpenTofu](https://opentofu.org/docs/intro/install/) 1.6 or newer.
- OTC account with AK/SK credentials, GPU quota and capacity in the selected AZ.
- An SSH public key and your public IPv4 CIDR (typically `x.x.x.x/32`).
- Outbound access to Ubuntu package mirrors, GitHub, PyTorch and Hugging Face.

The default image and GPU flavor must be available together in your tenant.
`p2s.2xlarge.8` (V100, 32 GiB VRAM) or a suitable P5 flavor are alternatives.
Use a compatible Ubuntu 22.04 x86_64 image with cloud-init and GPU passthrough;
GRID/vGPU flavors require a different driver setup. CPU-only flavors are rejected.

## Deploy

Copy `terraform.tfvars.example` to `terraform.tfvars` and set at least
`domain_name`, `public_key`, `ssh_allowed_cidr`, and an available GPU
`flavor_id`/`availability_zone1`. Keep credentials out of version control:

```bash
export TF_VAR_access_key='YOUR_ACCESS_KEY'
export TF_VAR_secret_key='YOUR_SECRET_KEY'

tofu init
tofu fmt -check main.tf variables.tf provider.tf outputs.tf migrations.tf
tofu validate
tofu plan -out=ncm.tfplan
tofu apply ncm.tfplan
tofu output -raw ssh_command
```

`tofu apply` provisions the infrastructure; cloud-init continues installing
software and checkpoints afterwards. The WebUI starts once installation
completes. On first boot cloud-init schedules a driver reboot.
Connect again after the reboot and check progress:

```bash
sudo cloud-init status --wait
sudo less /var/log/ncm-bootstrap.log
nvidia-smi
sudo systemctl status ncm-tinystories
sudo journalctl -u ncm-tinystories -f
```

The service runs the upstream `evaluate.py` with the TinyStories checkpoint on
GPU 0, checks a real CUDA operation, and scores generations using GPT-2 large.
With the defaults it creates 16 stories **per seed** across five seeds (80 total).
Each run gets a directory under `/opt/ncm/results/`, with `latest` pointing at
the most recent run. Files include `stories.jsonl` (`seed` and `text` per line),
`evaluation.log`, and `shard_0.log`. A completed oneshot service shows
`active (exited)`. To run it again:

```bash
sudo systemctl restart ncm-tinystories
```

## Story WebUI (German by default)

After cloud-init finishes and the ECS reboots, open the URL from:

```bash
tofu output -raw webui_url
```

At `/`, enter a German story prompt (pre-filled with **wildgewordene Roboter**),
choose maximum new tokens, temperature and top-p, then select **Geschichte
generieren**. The first request downloads the Qwen model to the ECS cache.
While it generates, the page refreshes every five seconds; the completed story
is shown in the browser and saved as a text file in `/opt/ncm/results/`. Recent
German stories are listed on the same page. The first generation can take longer
while the Qwen model downloads; the job log and any generation error are shown
on the start page.

Use the **NCM TinyStories (Englisch)** link to reach `/ncm`. That optional page
starts an upstream NCM evaluation with configurable **stories per seed** and
**generation batch size**, shows the most recent 30 runs, up to 100 saved stories
per run, and the evaluation and shard logs. NCM TinyStories is unconditional:
this page has no prompt field and generates English stories. The two web actions
and the systemd NCM evaluation runner use the same GPU lock (a simultaneous
second run exits without starting generation).

This lab WebUI listens on `0.0.0.0:8080` and is reachable via the ECS floating
IP over plain HTTP with no login. `webui_allowed_cidr` defaults to `0.0.0.0/0`;
set it to your client network if you want to limit access. Check the service
on the ECS with:

```bash
sudo systemctl status ncm-webui
sudo journalctl -u ncm-webui -f
```

If the URL returns **Connection refused** on an existing ECS, check whether
the service was installed and started: changing OpenTofu cloud-init user data
does not rerun cloud-init on an already booted instance. To install or update
the German story WebUI in place, without replacing the ECS:

```bash
# Locally, in the repository:
scp files/ncm-webui.py files/ncm-webui.service files/deutsche-geschichte.py \
  "ubuntu@$(tofu output -raw public_ip):/tmp/"
# On the ECS:
sudo install -o ncm -g ncm -m 755 /tmp/ncm-webui.py /opt/ncm/ncm-webui.py
sudo install -o ncm -g ncm -m 755 /tmp/deutsche-geschichte.py /opt/ncm/deutsche-geschichte.py
sudo install -m 644 /tmp/ncm-webui.service /etc/systemd/system/ncm-webui.service
sudo systemctl daemon-reload
sudo systemctl enable --now ncm-webui
sudo systemctl restart ncm-webui
sudo systemctl status ncm-webui
```

If the service fails, inspect `sudo journalctl -u ncm-webui -n 100 --no-pager`
on the ECS. Confirm the local listener with `curl http://127.0.0.1:8080/`
before checking the floating IP and security group.

For an **existing ECS**, installing only the WebUI avoids recreating the GPU
instance (OpenTofu user-data changes can replace its root disk):

```bash
# Locally, in the repository:
python3 - <<'PY' > /tmp/ncm-tinystories
import json
import subprocess

command = ["tofu", "console", "-no-color"]
expression = '''jsonencode(templatefile("files/ncm-tinystories.sh.tftpl", {eval_samples = var.eval_samples, eval_batch_size = var.eval_batch_size}))'''
result = subprocess.run(command, input=expression + "\n", text=True, capture_output=True, check=True)
print(json.loads(json.loads(result.stdout.strip().splitlines()[-1])), end="")
PY
scp files/ncm-webui.py files/ncm-webui.service files/deutsche-geschichte.py /tmp/ncm-tinystories \
  "ubuntu@$(tofu output -raw public_ip):/tmp/"
# On the ECS:
sudo install -o ncm -g ncm -m 755 /tmp/deutsche-geschichte.py /opt/ncm/deutsche-geschichte.py
sudo install -o ncm -g ncm -m 755 /tmp/ncm-webui.py /opt/ncm/ncm-webui.py
sudo install -m 644 /tmp/ncm-webui.service /etc/systemd/system/ncm-webui.service
sudo install -m 755 /tmp/ncm-tinystories /usr/local/bin/ncm-tinystories
sudo systemctl daemon-reload
sudo systemctl enable --now ncm-webui
```

The snippet renders the runner from the local OpenTofu variables. For public
access on an existing ECS, also open TCP/8080 on its OTC security group. First
inspect `tofu plan` for an ECS replacement; if one is planned, add the rule via
the OTC console instead of applying an unwanted instance replacement. This
manual copy is a one-time update; OpenTofu still tracks the original user data.

For the full upstream sample count, set `eval_samples = 256` in your tfvars.
`eval_batch_size` controls generation memory use; the upstream GPT-2 scoring
batch size is separate. Changing these variables updates cloud-init user data
and may replace the instance. For one-off runs without changing infrastructure:

```bash
sudo -u ncm -H bash
cd /opt/ncm/repo
export HF_HOME=/opt/ncm/cache CUDA_VISIBLE_DEVICES=0
/opt/ncm/venv/bin/python evaluate.py \
  --config /opt/ncm/artifacts/tinystories/config.yaml \
  --checkpoint-dir /opt/ncm/artifacts/tinystories \
  --gpus 0 --n 32 --bs 4 --out /opt/ncm/results/manual-01
```

Use a fresh output directory for each run. Installed Python package versions
are recorded in `/opt/ncm/installed-requirements.txt`.

## Beispiel: Eine deutsche Geschichte über wildgewordene Roboter

Das veröffentlichte TinyStories-Modell von [NCM](https://github.com/HazyResearch/ncm)
erzeugt englische Texte **ohne frei wählbaren Prompt**. Für eine Geschichte mit
vorgegebenem Thema nutzt das zusätzlich mitinstallierte Skript ein anderes,
deutschfähiges Modell: Qwen2.5-1.5B-Instruct. Beim ersten Start lädt es dieses
Modell in den bestehenden Hugging-Face-Cache auf der ECS.

Für die Geschichte über wildgewordene Roboter kannst du direkt die WebUI
(`tofu output -raw webui_url`) öffnen: Der Beispiel-Prompt ist bereits eingetragen.
Passe das Thema an und klicke auf **Geschichte generieren**. Alternativ verbinde
dich per SSH mit der ECS (`tofu output -raw ssh_command`) und nutze die CLI:

```bash
sudo -u ncm -H env HF_HOME=/opt/ncm/cache CUDA_VISIBLE_DEVICES=0 \
  /opt/ncm/venv/bin/python /opt/ncm/deutsche-geschichte.py \
  "Schreibe eine spannende, humorvolle Geschichte über wildgewordene Roboter, die eine Kleinstadt übernehmen. Ein Kind findet einen überraschenden Weg, sie zu stoppen. Mit Anfang, Wendung und Schluss."
```

Die Geschichte erscheint im Terminal und wird unter
`/opt/ncm/results/geschichte-<Zeit>.txt` gespeichert. `--max-new-tokens 600`
verlängert die mögliche Ausgabe, `--temperature 0.9` macht sie abwechslungsreicher
und `--seed 42` erleichtert vergleichbare Versuche.

Für mehrere Geschichten ohne erneutes Laden des Modells gibt es die TUI:

```bash
sudo -u ncm -H env HF_HOME=/opt/ncm/cache CUDA_VISIBLE_DEVICES=0 \
  /opt/ncm/venv/bin/python /opt/ncm/deutsche-geschichte.py --tui
```

**E** bearbeitet den Prompt (Enter übernehmen, Esc abbrechen), **G** generiert,
Pfeiltasten/Bild-auf/-ab scrollen die Geschichte. **<**/**>** ändern die
Token-Obergrenze, **-**/**+** die Temperatur und **[**/**]** `top-p`. **Q**
beendet die TUI nach einem laufenden Generierungsschritt. Jede Geschichte
wird automatisch als eigene Textdatei gespeichert. Am besten den NCM-Job erst
abschließen lassen, damit beide Modelle nicht gleichzeitig GPU-Speicher belegen.

Falls die ECS **bereits vor dieser Änderung** bereitgestellt wurde, kannst du
nur die aktualisierte Datei nachkopieren, ohne sie neu aufzubauen:

```bash
# Auf deinem lokalen Rechner im Repository:
scp files/deutsche-geschichte.py "ubuntu@$(tofu output -raw public_ip):/tmp/deutsche-geschichte.py"
# Auf der ECS:
sudo install -o ncm -g ncm -m 755 /tmp/deutsche-geschichte.py /opt/ncm/deutsche-geschichte.py
```

## Operations and lifecycle

The WebUI uses the floating IP on port 8080; SSH remains available for
operations.

To stop or restart the GPU ECS while keeping the infrastructure, run these
commands **from the repository directory**, using the same `terraform.tfvars`
and OTC credentials as for deployment:

```bash
tofu apply -var='power_state=shutoff'  # stop GPU billing; disk/EIP may still cost money
tofu apply -var='power_state=active'
```

To remove **all resources in this OpenTofu state**, first download any stories
you want to keep. Then, from the repository directory:

```bash
scp -r "ubuntu@$(tofu output -raw public_ip):/opt/ncm/results/" ./ncm-results
tofu init                 # only needed if this working directory has not been initialized
tofu plan -destroy        # inspect what will be removed
tofu destroy
```

`tofu destroy` reads `terraform.tfvars` automatically, prompts for confirmation
and deletes the ECS including its root disk, the floating IP and the other
resources it manages. Set `TF_VAR_access_key` and `TF_VAR_secret_key` again if
you supplied them as environment variables during deployment. Do not use the
saved deployment plan (`ncm.tfplan`) for destroying resources.

If migrating state from the original kubeadm-based version of this repository,
`migrations.tf` maps renamed resources to the existing state. Keep the previous
`environment` and network settings to reuse shared resources.
The GPU ECS replaces the old kubeadm ECS and its root disk; inspect the plan
and back up anything you need before applying it.

Local checks: `tofu fmt -check main.tf variables.tf provider.tf outputs.tf migrations.tf`
and `tofu validate`. Full generation requires
an OTC GPU ECS. See [the upstream NCM README](https://github.com/HazyResearch/ncm#readme)
for the model architecture, checkpoints, and evaluation protocol.
