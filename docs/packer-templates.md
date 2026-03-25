# Création des templates VM avec Packer

Stack Deployer repose sur des templates VM pré-configurés sur Proxmox.
Voici comment les créer avec [Packer](https://www.packer.io/).

## Prérequis

- Packer 1.10+
- Plugin Proxmox : `packer plugins install github.com/hashicorp/proxmox`
- ISO Windows Server 2022 et/ou Debian 12 sur le stockage Proxmox
- Un fichier `autounattend.xml` (Windows) ou `preseed.cfg`/cloud-init (Debian)

## Template Windows Server 2022

```hcl
# win2022.pkr.hcl
source "proxmox-iso" "win2022" {
  proxmox_url              = "https://192.168.1.100:8006/api2/json"
  username                 = "root@pam"
  token                    = "packer"
  token_secret             = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
  insecure_skip_tls_verify = true
  node                     = "pve"

  iso_file    = "local:iso/SERVER_EVAL_x64FRE_en-us.iso"
  iso_storage = "local"

  vm_name    = "win2022-tpl"
  vm_id      = 9000
  cores      = 2
  memory     = 4096
  os         = "win11"

  scsi_controller = "virtio-scsi-single"
  disks {
    disk_size    = "60G"
    storage_pool = "local-lvm"
    type         = "scsi"
  }

  network_adapters {
    bridge = "vmbr0"
    model  = "virtio"
  }

  additional_iso_files {
    device           = "sata1"
    iso_file         = "local:iso/virtio-win.iso"
    iso_storage_pool = "local"
    unmount          = true
  }

  communicator   = "winrm"
  winrm_username = "Administrator"
  winrm_password = "P@ssw0rd!"
  winrm_timeout  = "30m"

  cd_files = ["autounattend.xml"]
  cd_label = "OEMDRV"

  template_name        = "win2022-tpl"
  template_description = "Windows Server 2022 — sysprep + WinRM ready"
}

build {
  sources = ["source.proxmox-iso.win2022"]

  # Install VirtIO drivers
  provisioner "powershell" {
    inline = [
      "Set-ExecutionPolicy Bypass -Scope Process -Force",
      "Enable-PSRemoting -Force",
      "winrm set winrm/config/service '@{AllowUnencrypted=\"true\"}'",
      "winrm set winrm/config/service/auth '@{Basic=\"true\"}'",
    ]
  }

  # Install Windows updates
  provisioner "windows-update" {}

  # Sysprep
  provisioner "powershell" {
    inline = [
      "& $env:SystemRoot\\System32\\Sysprep\\Sysprep.exe /oobe /generalize /shutdown /quiet",
    ]
  }
}
```

## Template Debian 12 (cloud-init)

```hcl
# debian12.pkr.hcl
source "proxmox-iso" "debian12" {
  proxmox_url              = "https://192.168.1.100:8006/api2/json"
  username                 = "root@pam"
  token                    = "packer"
  token_secret             = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
  insecure_skip_tls_verify = true
  node                     = "pve"

  iso_file = "local:iso/debian-12-amd64-netinst.iso"

  vm_name    = "debian12-tpl"
  vm_id      = 9001
  cores      = 2
  memory     = 2048
  os         = "l26"

  scsi_controller = "virtio-scsi-single"
  disks {
    disk_size    = "20G"
    storage_pool = "local-lvm"
    type         = "scsi"
  }

  network_adapters {
    bridge = "vmbr0"
    model  = "virtio"
  }

  cloud_init              = true
  cloud_init_storage_pool = "local-lvm"

  ssh_username = "root"
  ssh_password = "packer"
  ssh_timeout  = "20m"

  boot_command = [
    "<esc><wait>",
    "auto url=http://{{ .HTTPIP }}:{{ .HTTPPort }}/preseed.cfg<enter>"
  ]
  http_directory = "http"

  template_name        = "debian12-tpl"
  template_description = "Debian 12 — cloud-init ready"
}

build {
  sources = ["source.proxmox-iso.debian12"]

  provisioner "shell" {
    inline = [
      "apt-get update && apt-get upgrade -y",
      "apt-get install -y qemu-guest-agent cloud-init python3 python3-apt sudo",
      "systemctl enable qemu-guest-agent",
      "systemctl enable cloud-init",
      "apt-get clean",
      "cloud-init clean",
    ]
  }
}
```

## Templates attendus par les stacks

| Nom template    | OS                  | Utilisé par            |
|-----------------|---------------------|------------------------|
| `win2022-tpl`   | Windows Server 2022 | Lab AD, SOC Lab (cible)|
| `win11-tpl`     | Windows 11          | Lab AD (poste client)  |
| `debian12-tpl`  | Debian 12           | SOC, Web, Monitoring   |
| `ubuntu24-tpl`  | Ubuntu 24.04        | Dev Platform (option)  |

## Commandes

```bash
# Valider
packer validate win2022.pkr.hcl

# Construire
packer build win2022.pkr.hcl

# Construire avec variables
packer build -var "proxmox_url=https://10.0.0.1:8006/api2/json" win2022.pkr.hcl
```
