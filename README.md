# TP — Blockchain de Zéro (Master 1 — ESGI)

**Groupe :** Hugo Rayaume, Enzo Ravignon, Louis Baudat  
**Cours :** Blockchain — Master 1 ESGI (Joffrey Hérard)

Implémentation complète en Python d'une **blockchain décentralisée** dotée d'un algorithme de consensus **Proof of Work (PoW)**, d'une **API REST Flask**, d'un **réseau pair-à-pair (P2P) multi-nœuds** conteneurisé sous **Docker**, et d'un **Dashboard Web interactif (Blockchain Explorer)**.

---

## Sommaire
1. [Architecture du Projet](#1-architecture-du-projet)
2. [Algorithme de Consensus Choisi et Justification](#2-algorithme-de-consensus-choisi-et-justification)
3. [Installation et Lancement du Projet](#3-installation-et-lancement-du-projet)
4. [Guide de Démonstration (Les 5 Preuves du TP)](#4-guide-de-démonstration-les-5-preuves-du-tp)
5. [Référence de l'API REST Flask](#5-référence-de-lapi-rest-flask)
6. [Difficultés Rencontrées et Solutions Apportées](#6-difficultés-rencontrées-et-solutions-apportées)

---

## 1. Architecture du Projet

```text
blockchain/
├── blockchain.py        # Classes Block et Blockchain (SHA-256 déterministe, PoW, validation, P2P)
├── app.py               # Serveur Flask (API REST + routes du Dashboard Web)
├── demo.py              # Script automatisé validant les 5 preuves exigées par le sujet
├── requirements.txt     # Dépendances Python (Flask, requests)
├── Dockerfile           # Image Docker d'un nœud Blockchain
├── docker-compose.yml   # Déploiement multi-nœuds (3 PC : pc-hugo, pc-enzo, pc-louis)
├── templates/
│   └── index.html       # Interface du Dashboard Web (Blockchain Explorer)
└── static/
    ├── style.css        # Thème et styles du Dashboard
    └── app.js           # Logique front-end temps réel (API fetch, P2P, audit de sécurité)
```

### Structure d'un Bloc (`Block`)
Chaque bloc de la chaîne contient les champs suivants :
* `index` (`int`) : Position du bloc dans la chaîne (`0` pour le bloc Genesis).
* `timestamp` (`float`) : Horodatage UNIX de création du bloc.
* `transactions` (`list`) : Liste des transactions validées dans le bloc (`sender`, `recipient`, `amount`).
* `previous_hash` (`str`) : Empreinte SHA-256 du bloc précédent (garantit le chaînage cryptographique).
* `nonce` (`int`) : Champ de consensus incrémenté lors de la Preuve de Travail (*Proof of Work*).
* `hash` (`str`) : Empreinte SHA-256 propre du bloc, calculée de manière déterministe via `json.dumps(..., sort_keys=True)`.

---

## 2. Algorithme de Consensus Choisi et Justification

### Choix : **Proof of Work (PoW — Preuve de Travail)**

Nous avons retenu et implémenté l'algorithme **Proof of Work (PoW)** avec une difficulté configurable (par défaut `difficulty = 4`, exigeant que le hash SHA-256 de chaque bloc commence par quatre zéros : `0000...`).

### Justification :
1. **Asymétrie cryptographique (Coûteux à calculer, instantané à vérifier)** :
   Pour forger un bloc valide, un nœud mineur doit tester en moyenne $16^4 = 65\,536$ valeurs de `nonce` par force brute jusqu'à obtenir un hash commençant par `0000`. En revanche, n'importe quel autre nœud du réseau vérifie la validité de cette preuve en **un seul calcul SHA-256** (`block.compute_hash()`).
2. **Immuabilité et détection immédiate de falsification** :
   Si un attaquant modifie rétroactivement le montant d'une transaction dans un bloc $i$, le hash recalculé de ce bloc change radicalement (effet avalanche de SHA-256) et ne correspond plus au hash stocké ni à la cible `0000...`. Même s'il re-minait le bloc $i$, son nouveau hash invaliderait le champ `previous_hash` du bloc $i+1$ et de tous les blocs suivants.
3. **Convergence en réseau distribué sans tiers de confiance** :
   Associé à la règle de la chaîne valide la plus longue (*Nakamoto Consensus* dans `/nodes/resolve`), le Proof of Work permet à des nœuds en désaccord de converger de manière objective vers une vérité unique.
4. **Pertinence face aux alternatives dans le cadre du TP** :
   Contrairement au *Proof of Authority (PoA)* qui repose sur des validateurs pré-approuvés (centralisé) ou au *Proof of Stake (PoS)* qui nécessite une distribution initiale de jetons dès le bloc Genesis (problème du *nothing at stake* et du *cold start*), le PoW permet à n'importe quel nouveau nœud Docker ou PC du réseau de participer immédiatement au consensus.

---

## 3. Installation et Lancement du Projet

### Option A — Réseau Multi-PC avec Docker Compose (Recommandé)

Le fichier `docker-compose.yml` lance **3 nœuds isolés** (`pc-hugo`, `pc-enzo`, `pc-louis`) interconnectés sur un réseau virtuel Docker `blockchain-net` :

```bash
docker compose up -d --build
```

Ouvrez ensuite les 3 nœuds dans votre navigateur :
* 💻 **PC de Hugo (`pc-hugo`)** : [http://localhost:5001](http://localhost:5001)
* 💻 **PC d'Enzo (`pc-enzo`)** : [http://localhost:5002](http://localhost:5002)
* 💻 **PC de Louis (`pc-louis`)** : [http://localhost:5003](http://localhost:5003)

Pour arrêter les conteneurs :
```bash
docker compose down
```

### Option B — Connecter plusieurs vrais PC physiques sur le même réseau Wi-Fi / LAN

Sur chaque PC physique connecté au même réseau local :
```bash
docker build -t tp-blockchain .
docker run -d -p 5000:5000 -e NODE_ID=PC-Hugo tp-blockchain
```
Chaque Dashboard affiche en haut son adresse IP locale (ex. `http://192.168.1.42:5000`). Entrez l'adresse IP de l'autre PC dans la section **Réseau** et cliquez sur **Connecter** pour échanger des transactions entre machines physiques.

### Option C — Lancement local avec Python (`venv`)

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Lancer un nœud sur le port 5000
.venv/bin/python app.py --port 5000 --node-id noeud-local
```

---

## 4. Guide de Démonstration (Les 5 Preuves du TP)

### 1. Via le script automatisé (`demo.py`)
Le script `demo.py` exécute et vérifie automatiquement les **5 preuves demandées** (incluant le démarrage de 2 serveurs Flask réels pour prouver la résolution de conflits HTTP) :
```bash
.venv/bin/python demo.py
```

### 2. En direct depuis le Dashboard Web (`http://localhost:5001` & `http://localhost:5002`)
1. **Création d'un bloc et vérification du chaînage** :
   Cliquez sur **Miner un bloc**. Le **Bloc #1** apparaît : sa ligne `PRÉC` est strictement identique au `HASH` du **Bloc #0 (Genesis)**.
2. **Ajout de transactions puis minage d'un bloc les contenant** :
   Sélectionnez un émetteur (`pc-hugo`) et un destinataire du réseau (`pc-enzo` ou `pc-louis`), indiquez un montant et cliquez sur **Envoyer sur le réseau**. La transaction apparaît dans la *Mempool* de tous les PC connectés. Cliquez sur **Miner un bloc** : la transaction est inscrite dans le bloc et les **Soldes actifs** sont mis à jour.
3. **Détection d'une chaîne falsifiée (bloc modifié → chaîne invalide)** :
   Cliquez sur le bouton **« Falsifier un bloc »** (qui modifie le montant d'une transaction dans un bloc existant). Le bloc falsifié passe en rouge et le statut du nœud affiche immédiatement **« Chaîne Altérée »**. Cliquez sur **« Restaurer »** pour rétablir l'intégrité.
4. **Validité du consensus (bloc au consensus invalide rejeté)** :
   Cliquez sur **« Bloc PoW invalide »** (qui soumet un bloc avec `nonce = 0` ne respectant pas le préfixe `0000`). Le serveur rejette le bloc et affiche le motif du refus.
5. **Résolution de conflits (deux nœuds en désaccord convergent)** :
   Sur `pc-hugo` (`5001`), décochez *« Diffuser le bloc miné aux autres PC »* et minez 2 blocs. `pc-hugo` possède désormais une chaîne plus longue que `pc-enzo` (`5002`). Sur `pc-enzo`, cliquez sur **« Synchroniser (Résoudre conflits) »** : `pc-enzo` adopte la chaîne valide la plus longue de `pc-hugo`.

---

## 5. Référence de l'API REST Flask

| Méthode | Route | Description |
| :--- | :--- | :--- |
| `GET` | `/chain` | Retourne la chaîne complète, sa longueur, sa validité, la mempool, les soldes et les membres du réseau. |
| `POST` | `/transactions/new` | Ajoute une transaction (`sender`, `recipient`, `amount`) entre membres du réseau et la diffuse en P2P. |
| `GET` | `/mine` | Exécute le Proof of Work, forge un nouveau bloc avec la mempool (+ récompense) et l'ajoute à la chaîne. |
| `GET` | `/nodes` | Liste l'identifiant du nœud et les pairs enregistrés. |
| `POST` | `/nodes/register` | Enregistre un ou plusieurs nœuds pairs (`{"nodes": ["http://127.0.0.1:5002"]}`). |
| `GET` | `/nodes/resolve` | Résout les conflits en adoptant la chaîne valide la plus longue parmi les pairs enregistrés. |
| `GET` | `/validate` | Vérifie l'intégrité cryptographique complète de la chaîne locale. |
| `POST` | `/blocks/add` | Valide et ajoute un bloc reçu d'un pair (rejette tout bloc dont le chaînage ou le PoW est invalide). |

---

## 6. Difficultés Rencontrées et Solutions Apportées

1. **Déterminisme du hachage SHA-256 entre différents nœuds** :
   * *Problème* : En Python, la sérialisation d'un dictionnaire JSON peut varier si l'ordre des clés ou les séparateurs diffèrent d'une exécution à l'autre, ce qui fausserait la vérification du hash d'un bloc reçu par le réseau.
   * *Solution* : Utilisation stricte de `json.dumps(block_content, sort_keys=True, separators=(",", ":"))` dans `Block.compute_hash()`, garantissant que chaque nœud obtient exactement la même empreinte SHA-256 pour un même bloc.
2. **Cohérence du Bloc Genesis sur un réseau décentralisé** :
   * *Problème* : Si chaque conteneur Docker génère son bloc Genesis avec `time.time()` au moment de son lancement, chaque nœud aura un bloc Genesis avec un hash différent, empêchant la validation croisée des chaînes lors de `/nodes/resolve`.
   * *Solution* : Définition d'un bloc Genesis déterministe à l'index `0` (également validé par Proof of Work), assurant que tous les nœuds partagent la même racine cryptographique.
3. **Validation des acteurs du réseau sur les transactions** :
   * *Problème* : Permettre la saisie libre de n'importe quelle chaîne de caractères pour `sender` et `recipient` autorisait la création de transactions vers des entités inexistantes.
   * *Solution* : Implémentation d'une découverte automatique des identifiants des nœuds pairs (`get_network_members()`) couplée à une validation côté API et à des menus déroulants dynamiques sur le Dashboard.
4. **Sécurité lors de la résolution de conflits (`/nodes/resolve`)** :
   * *Problème* : Un nœud pair malveillant pourrait annoncer une chaîne plus longue mais contenant des blocs non minés ou altérés.
   * *Solution* : Avant d'adopter une chaîne plus longue, `resolve_conflicts()` exécute systématiquement `is_valid_chain(candidate_chain)` qui recalcule le hash propre, vérifie le `previous_hash` et contrôle la preuve de travail (`0000...`) de chaque bloc.
