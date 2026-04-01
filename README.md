# Stack Deployer

**Portail self-service de deploiement de stacks VM sur Proxmox VE**

> Selectionnez une stack, choisissez vos services, deployez. Automatiquement.

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?logo=fastapi)
![Vue.js](https://img.shields.io/badge/Vue.js-3.4+-4FC08D?logo=vuedotjs)
![Proxmox](https://img.shields.io/badge/Proxmox-8.x+-E57000?logo=proxmox)
![Ansible](https://img.shields.io/badge/Ansible-2.16+-EE0000?logo=ansible)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## Concept

Stack Deployer est une application web permettant de provisionner des environnements complets (stacks de VMs) sur un hyperviseur Proxmox VE, avec selection granulaire des services a deployer.

**Pas besoin de templates VM** : les VMs sont creees automatiquement a partir d'images cloud officielles (Debian, Ubuntu) telechargees sur Proxmox a la volee.

**Cas d'usage :**
- Deployer un lab Active Directory complet (DC + CA + serveur membre) en un clic
- Monter un SOC lab (Wazuh + TheHive + MISP) pour des exercices de cybersecurite
- Creer une stack web (Nginx + PHP + MariaDB + Redis) pour du developpement

## Architecture

```
+-------------------------------------+
|   Frontend  -  Vue.js + Tailwind    |
|   Stack catalog, service picker,    |
|   deployment dashboard, live logs   |
+----------------+--------------------+
                 | REST API / WebSocket
+----------------v--------------------+
|   Backend  -  FastAPI (Python)      |
|   Stack engine, orchestration,      |
|   auth, task queue (Celery/Redis)   |
+--------+------------------+--------+
         |                  |
   Proxmox API        SSH + Ansible
   (create VMs)       (configure roles)
         |                  |
+--------v------------------v--------+
|   Proxmox VE                       |
|   Cloud images auto-download       |
|   (Debian 12, Ubuntu 22/24...)     |
+------------------------------------+
```

## Images cloud supportees

Les VMs sont creees depuis des images cloud officielles, telechargees automatiquement sur Proxmox lors du premier deploiement :

| Nom interne | Image | User par defaut |
|-------------|-------|-----------------|
| `debian12-tpl` | Debian 12 generic | root |
| `debian11-tpl` | Debian 11 generic | root |
| `ubuntu2204-tpl` | Ubuntu 22.04 cloud | ubuntu |
| `ubuntu2404-tpl` | Ubuntu 24.04 cloud | ubuntu |

> Le login et mot de passe des VMs sont definis lors du deploiement via cloud-init.

## Stacks disponibles

| Stack | VMs | Services |
|-------|-----|----------|
| **Lab AD complet** | DC01, CA01, SRV01 | AD DS, DNS, DHCP, AD CS, IIS |
| **SOC Lab** | SIEM01, IR01, TI01... | Wazuh, TheHive, MISP, Cortex |
| **Web Stack** | WEB01, DB01 | Nginx, PHP-FPM, MariaDB, Redis |
| **Monitoring** | MON01 | Prometheus, Grafana, Loki, AlertManager |
| **Dev Platform** | DEV01, GIT01 | Gitea, Jenkins, SonarQube, Registry |

## Prerequis

- **Proxmox VE 8.x+** avec un token API
- **Machine hote** (Linux) avec :
  - Docker + Docker Compose v2
  - Acces SSH vers le serveur Proxmox (cle SSH)

## Installation

### 1. Cloner le projet

```bash
git clone https://github.com/MrVindicte/stack-deployer.git
cd stack-deployer
```

### 2. Configurer l'environnement

```bash
make setup
# Cela cree backend/.env depuis backend/.env.example
```

Editez `backend/.env` et modifiez **obligatoirement** ces valeurs :

| Variable | Description | Ou la trouver |
|----------|-------------|---------------|
| `SECRET_KEY` | Cle secrete de l'app | Generer avec `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `POSTGRES_PASSWORD` | Mot de passe PostgreSQL | Choisir un mot de passe fort |
| `DATABASE_URL` | URL de connexion DB | Remplacer `VOTRE_MOT_DE_PASSE_POSTGRES` par le meme mot de passe que `POSTGRES_PASSWORD` |
| `PROXMOX_HOST` | IP de votre Proxmox | ex: `192.168.1.100` |
| `PROXMOX_TOKEN_NAME` | Nom du token API | Celui cree dans Proxmox |
| `PROXMOX_TOKEN_VALUE` | Valeur UUID du token | Affichee une seule fois a la creation |
| `PROXMOX_DEFAULT_NODE` | Nom du noeud Proxmox | Visible dans Datacenter > votre noeud |
| `FIRST_ADMIN_PASSWORD` | Mot de passe admin | Choisir un mot de passe fort |

### 3. Creer le token API Proxmox

Dans l'interface Proxmox :
1. **Datacenter > Permissions > API Tokens > Add**
2. User : `root@pam`
3. Token ID : `stackdeployer` (ou le nom de votre choix)
4. **Decocher "Privilege Separation"** (important !)
5. Copier la Token Value dans `PROXMOX_TOKEN_VALUE`

### 4. Configurer SSH vers Proxmox

Le conteneur Celery doit pouvoir faire SSH vers Proxmox pour importer les disques cloud :

```bash
# Generer une cle SSH si vous n'en avez pas
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N ""

# Copier la cle sur Proxmox (mot de passe root Proxmox demande)
ssh-copy-id root@VOTRE_IP_PROXMOX

# Tester
ssh root@VOTRE_IP_PROXMOX "hostname"
```

### 5. Lancer l'application

```bash
# Exporter les variables necessaires a docker-compose
export POSTGRES_PASSWORD='votre_mot_de_passe'
export SSH_KEY_DIR='/root/.ssh'  # ou ~/.ssh

# Demarrer tous les services
make up
```

### 6. Acceder a l'interface

- **Frontend** : `http://VOTRE_IP:5173`
- **API Docs** : `http://VOTRE_IP:8000/docs`
- **Login** : `admin` / le mot de passe defini dans `FIRST_ADMIN_PASSWORD`

> Si le firewall bloque les ports : `ufw allow 5173/tcp && ufw allow 8000/tcp`

## Utilisation

1. Se connecter au dashboard
2. Aller dans **Catalogue** et choisir une stack
3. Selectionner les services souhaites
4. Modifier les specs des VMs si besoin (CPU, RAM, disque) en cliquant dessus
5. Renseigner le **login** et **mot de passe** des VMs (obligatoire)
6. Cliquer sur **Lancer le deploiement**
7. Suivre la progression dans les logs en temps reel
8. Les identifiants sont consultables dans le detail du deploiement

## Structure du projet

```
stack-deployer/
  backend/
    app/
      api/            # Endpoints FastAPI
      core/           # Config, security, celery
      models/         # SQLAlchemy models
      schemas/        # Pydantic schemas
      services/       # Business logic (Proxmox, Ansible, deployer)
    ansible/
      roles/          # Roles Ansible (ad-ds, ad-cs, dns...)
      templates/      # Templates Jinja2
      inventories/    # Inventaires dynamiques
    stacks/           # Definitions YAML des stacks
    requirements.txt
    .env.example      # <-- A COPIER EN .env ET CONFIGURER
  frontend/
    src/
      components/     # Composants Vue reutilisables
      views/          # Pages principales
      stores/         # Pinia stores
      assets/         # Styles, images
    package.json
  docker/             # Docker Compose
  docs/               # Documentation additionnelle
  .github/workflows/  # CI/CD
```

## Commandes utiles

```bash
make help          # Voir toutes les commandes
make up            # Demarrer les services
make down          # Arreter les services
make logs          # Voir les logs de tous les services
make logs-backend  # Logs du backend
make logs-celery   # Logs du worker Celery
make shell         # Shell dans le conteneur backend
make migrate       # Appliquer les migrations DB
```

## License

MIT - voir [LICENSE](LICENSE)

## Auteur

Romain - Mastere Ingenieur en Informatique et Cybersecurite (ISRC 2025/2027)
