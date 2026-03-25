# 🖥️ Stack Deployer

**Portail self-service de déploiement de stacks VM sur Proxmox VE**

> Sélectionnez une stack, choisissez vos services, déployez. Automatiquement.

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?logo=fastapi)
![Vue.js](https://img.shields.io/badge/Vue.js-3.4+-4FC08D?logo=vuedotjs)
![Proxmox](https://img.shields.io/badge/Proxmox-8.x-E57000?logo=proxmox)
![Ansible](https://img.shields.io/badge/Ansible-2.16+-EE0000?logo=ansible)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## 📋 Concept

Stack Deployer est une application web permettant de provisionner des environnements complets (stacks de VMs) sur un hyperviseur Proxmox VE, avec sélection granulaire des services à déployer.

**Cas d'usage :**
- Déployer un lab Active Directory complet (DC + CA + serveur membre) en un clic
- Monter un SOC lab (Wazuh + TheHive + MISP) pour des exercices de cybersécurité
- Créer une stack web (Nginx + PHP + MariaDB + Redis) pour du développement

## 🏗️ Architecture

```
┌─────────────────────────────────────┐
│   Frontend — Vue.js + Tailwind CSS  │
│   Stack catalog, service picker,    │
│   deployment dashboard, live logs   │
└──────────────┬──────────────────────┘
               │ REST API / WebSocket
┌──────────────▼──────────────────────┐
│   Backend — FastAPI (Python)        │
│   Stack engine, orchestration,      │
│   auth, task queue (Celery/Redis)   │
├──────────┬──────────────────────────┤
│          │              │           │
│  Proxmox API    Ansible Playbooks   │
│  (clone VMs)    (configure roles)   │
└──────────┴──────────┬───────────────┘
                      │
┌─────────────────────▼───────────────┐
│   Proxmox VE — Dell PowerEdge T630 │
│   VM templates (Win2022, Debian,    │
│   Ubuntu) + cloud-init              │
└─────────────────────────────────────┘
```

## 🚀 Quick Start

### Prérequis

- Python 3.11+
- Node.js 20+
- Redis (pour Celery)
- Proxmox VE 8.x avec API token
- Ansible 2.16+

### Installation

```bash
# Clone
git clone https://github.com/<username>/stack-deployer.git
cd stack-deployer

# Backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Configurer les variables

# Frontend
cd ../frontend
npm install

# Lancer en dev
# Terminal 1 — Backend
cd backend && uvicorn app.main:app --reload --port 8000

# Terminal 2 — Celery worker
cd backend && celery -A app.core.celery_app worker -l info

# Terminal 3 — Frontend
cd frontend && npm run dev
```

## 📁 Structure du projet

```
stack-deployer/
├── backend/
│   ├── app/
│   │   ├── api/            # Endpoints FastAPI
│   │   ├── core/           # Config, security, celery
│   │   ├── models/         # SQLAlchemy models
│   │   ├── schemas/        # Pydantic schemas
│   │   └── services/       # Business logic (Proxmox, Ansible)
│   ├── ansible/
│   │   ├── roles/          # Rôles Ansible (ad-ds, ad-cs, dns...)
│   │   ├── templates/      # Templates Jinja2
│   │   └── inventories/    # Inventaires dynamiques
│   ├── stacks/             # Définitions YAML des stacks
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/     # Composants Vue réutilisables
│   │   ├── views/          # Pages principales
│   │   ├── stores/         # Pinia stores
│   │   └── assets/         # Styles, images
│   └── package.json
├── docker/                 # Docker Compose pour dev/prod
├── docs/                   # Documentation additionnelle
└── .github/workflows/      # CI/CD
```

## 📦 Stacks disponibles

| Stack | VMs | Services |
|-------|-----|----------|
| **Lab AD complet** | DC01, CA01, SRV01 | AD DS, DNS, DHCP, AD CS, IIS |
| **SOC Lab** | SIEM01, THEHIVE01, MISP01 | Wazuh, TheHive, MISP, Cortex |
| **Web Stack** | WEB01, DB01 | Nginx, PHP-FPM, MariaDB, Redis |
| **Monitoring** | MON01 | Prometheus, Grafana, Loki, AlertManager |
| **Dev Platform** | DEV01, GIT01 | Gitea, Jenkins, SonarQube, Registry |

## 🔧 Configuration

Voir [`.env.example`](backend/.env.example) pour toutes les variables de configuration.

## 📄 License

MIT — voir [LICENSE](LICENSE)

## 👤 Auteur

Romain — Mastère Ingénieur en Informatique et Cybersécurité (ISRC 2025/2027)
