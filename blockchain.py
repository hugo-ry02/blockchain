"""
Module principal implémentant la structure d'un Bloc et la Blockchain avec Proof of Work (PoW).
TP — Blockchain de Zéro (Master 1 — ESGI)
"""

from __future__ import annotations

import copy
import hashlib
import json
import time
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

import requests


class Block:
    """
    Représente un bloc individuel dans la blockchain.

    Attributs :
        index (int) : Position du bloc dans la chaîne (0 pour le bloc Genesis).
        timestamp (float) : Horodatage UNIX de la création du bloc.
        transactions (List[Dict[str, Any]]) : Liste des transactions incluses dans le bloc.
        previous_hash (str) : Hash SHA-256 du bloc précédent dans la chaîne.
        nonce (int) : Champ de consensus (Preuve de Travail / Proof of Work).
        hash (str) : Hash SHA-256 propre du bloc, calculé de manière déterministe.
    """

    def __init__(
        self,
        index: int,
        transactions: List[Dict[str, Any]],
        previous_hash: str,
        timestamp: Optional[float] = None,
        nonce: int = 0,
        block_hash: Optional[str] = None,
    ) -> None:
        self.index: int = index
        self.timestamp: float = timestamp if timestamp is not None else round(time.time(), 6)
        self.transactions: List[Dict[str, Any]] = transactions
        self.previous_hash: str = previous_hash
        self.nonce: int = nonce
        self.hash: str = block_hash if block_hash is not None else self.compute_hash()

    def compute_hash(self) -> str:
        """
        Calcule le hash SHA-256 déterministe du bloc à partir de ses attributs
        (hors champ `hash` lui-même).
        L'option `sort_keys=True` garantit que l'ordre des clés JSON est toujours identique.
        """
        block_content = {
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": self.transactions,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
        }
        block_string = json.dumps(block_content, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(block_string.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise le bloc sous forme de dictionnaire (pour l'API JSON)."""
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": self.transactions,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
            "hash": self.hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Block":
        """Reconstruit une instance de `Block` à partir d'un dictionnaire JSON."""
        return cls(
            index=int(data["index"]),
            transactions=list(data["transactions"]),
            previous_hash=str(data["previous_hash"]),
            timestamp=float(data["timestamp"]),
            nonce=int(data.get("nonce", 0)),
            block_hash=str(data["hash"]),
        )


class Blockchain:
    """
    Gère la chaîne de blocs, les transactions en attente (mempool),
    le consensus par Preuve de Travail (Proof of Work) et la synchronisation multi-nœuds.
    """

    def __init__(self, difficulty: int = 4, node_id: Optional[str] = None) -> None:
        self.difficulty: int = difficulty
        self.node_id: Optional[str] = node_id
        self.chain: List[Block] = []
        self.pending_transactions: List[Dict[str, Any]] = []
        self.nodes: Set[str] = set()
        self.peer_ids: Dict[str, str] = {}
        # Sauvegarde interne permettant de restaurer la chaîne après une démo de falsification
        self._backup_chain: Optional[List[Block]] = None

        # Création automatique du bloc Genesis au démarrage
        self.create_genesis_block()

    @property
    def target_prefix(self) -> str:
        """Préfixe exigé par le Proof of Work (ex: '0000' pour difficulté = 4)."""
        return "0" * self.difficulty

    @property
    def last_block(self) -> Block:
        """Retourne le dernier bloc de la chaîne."""
        return self.chain[-1]

    def create_genesis_block(self) -> Block:
        """
        Génère le tout premier bloc de la chaîne (Bloc Genesis, index 0).
        Ses valeurs sont déterministes pour que plusieurs nœuds démarrés séparément
        partagent le même bloc d'origine.
        """
        genesis_block = Block(
            index=0,
            transactions=[
                {
                    "sender": "GENESIS",
                    "recipient": "RESEAU",
                    "amount": 0,
                }
            ],
            previous_hash="0" * 64,
            timestamp=1700000000.0,
            nonce=0,
        )
        # On applique le Proof of Work au bloc Genesis pour que toute la chaîne soit homogène
        genesis_block.hash = self.proof_of_work(genesis_block)
        self.chain.append(genesis_block)
        return genesis_block

    def get_network_members(self) -> List[str]:
        """
        Retourne la liste triée des identifiants de tous les nœuds présents dans le réseau
        (ce nœud + les pairs enregistrés).
        """
        members: Set[str] = set()
        if self.node_id:
            members.add(self.node_id)

        for node_url in list(self.nodes):
            if node_url not in self.peer_ids:
                try:
                    res = requests.get(f"{node_url}/nodes", timeout=0.6)
                    if res.status_code == 200:
                        remote_id = res.json().get("node_id")
                        if remote_id:
                            self.peer_ids[node_url] = str(remote_id)
                except requests.RequestException:
                    pass

            if node_url in self.peer_ids:
                members.add(self.peer_ids[node_url])
            else:
                parsed = urlparse(node_url)
                host = parsed.hostname or ""
                if host and host not in ("127.0.0.1", "localhost", "0.0.0.0"):
                    members.add(host)
                elif parsed.port:
                    members.add(f"node-{parsed.port}")

        return sorted(members)

    def add_transaction(
        self,
        sender: str,
        recipient: str,
        amount: float,
        allowed_members: Optional[Set[str]] = None,
    ) -> int:
        """
        Ajoute une nouvelle transaction dans la liste des transactions en attente.

        Retourne :
            int : L'index du prochain bloc dans lequel cette transaction sera minée.
        """
        if not sender or not str(sender).strip():
            raise ValueError("Le champ 'sender' (émetteur) est obligatoire.")
        if not recipient or not str(recipient).strip():
            raise ValueError("Le champ 'recipient' (destinataire) est obligatoire.")

        sender_clean = str(sender).strip()
        recipient_clean = str(recipient).strip()

        if sender_clean == recipient_clean:
            raise ValueError("L'émetteur et le destinataire doivent être deux nœuds différents.")

        if allowed_members is not None:
            if sender_clean not in allowed_members:
                raise ValueError(
                    f"Émetteur '{sender_clean}' non reconnu dans le réseau ({', '.join(sorted(allowed_members))})."
                )
            if recipient_clean not in allowed_members:
                raise ValueError(
                    f"Destinataire '{recipient_clean}' non reconnu dans le réseau ({', '.join(sorted(allowed_members))})."
                )

        try:
            numeric_amount = float(amount)
        except (TypeError, ValueError) as exc:
            raise ValueError("Le montant 'amount' doit être un nombre valide.") from exc

        if numeric_amount <= 0:
            raise ValueError("Le montant 'amount' doit être strictement positif.")

        transaction = {
            "sender": sender_clean,
            "recipient": recipient_clean,
            "amount": round(numeric_amount, 4),
        }
        self.pending_transactions.append(transaction)
        return self.last_block.index + 1

    def proof_of_work(self, block: Block) -> str:
        """
        Algorithme de consensus Proof of Work (Preuve de Travail).
        Incrémente `block.nonce` jusqu'à ce que le hash SHA-256 du bloc
        commence par `difficulty` zéros (ex: '0000...').
        """
        block.nonce = 0
        computed_hash = block.compute_hash()
        while not computed_hash.startswith(self.target_prefix):
            block.nonce += 1
            computed_hash = block.compute_hash()
        block.hash = computed_hash
        return computed_hash

    def is_valid_block(self, block: Block, previous_block: Block) -> tuple[bool, str]:
        """
        Vérifie qu'un nouveau bloc est valide par rapport au bloc précédent :
        1. Index consécutif
        2. Chaînage (`previous_hash` == `previous_block.hash`)
        3. Consensus Proof of Work respecté (préfixe '0000...')
        4. Hash propre intègre (`block.hash` == `block.compute_hash()`)
        """
        if block.index != previous_block.index + 1:
            return (
                False,
                f"Index invalide : attendu {previous_block.index + 1}, reçu {block.index}.",
            )

        if block.previous_hash != previous_block.hash:
            return (
                False,
                "Chaînage rompu : 'previous_hash' ne correspond pas au hash du bloc précédent.",
            )

        if not block.hash.startswith(self.target_prefix):
            return (
                False,
                f"Consensus PoW invalide : le hash ne commence pas par '{self.target_prefix}'.",
            )

        recalculated_hash = block.compute_hash()
        if block.hash != recalculated_hash:
            return (
                False,
                "Hash du bloc falsifié ou incohérent avec son contenu et son nonce.",
            )

        return True, "Bloc valide."

    def add_block(self, block: Block) -> tuple[bool, str]:
        """
        Vérifie et ajoute un bloc construit à la fin de la chaîne.
        Rejette tout bloc dont le chaînage ou le consensus est invalide.
        """
        is_valid, reason = self.is_valid_block(block, self.last_block)
        if not is_valid:
            return False, reason

        self.chain.append(block)
        # Retirer de la mempool locale les transactions qui viennent d'être validées dans ce bloc
        for mined_tx in block.transactions:
            if mined_tx in self.pending_transactions:
                self.pending_transactions.remove(mined_tx)
        return True, "Bloc ajouté avec succès."

    def mine_pending_transactions(self, miner_address: str = "miner-node-1") -> Block:
        """
        Crée un nouveau bloc contenant les transactions en attente + une récompense de minage,
        exécute le Proof of Work, l'ajoute à la chaîne et vide les transactions en attente.
        """
        # Ajout de la récompense de minage (coinbase transaction)
        reward_transaction = {
            "sender": "0 (Récompense Réseau)",
            "recipient": miner_address,
            "amount": 1.0,
        }
        transactions_to_mine = list(self.pending_transactions) + [reward_transaction]

        new_block = Block(
            index=self.last_block.index + 1,
            transactions=transactions_to_mine,
            previous_hash=self.last_block.hash,
        )

        # Exécution du consensus Proof of Work
        self.proof_of_work(new_block)

        # Vérification et ajout à la chaîne
        success, reason = self.add_block(new_block)
        if not success:
            raise RuntimeError(f"Erreur lors de l'ajout du bloc miné : {reason}")

        # Réinitialisation de la mempool
        self.pending_transactions = []
        return new_block

    def is_valid_chain(self, chain: Optional[List[Block]] = None) -> tuple[bool, str]:
        """
        Vérifie l'intégrité complète d'une chaîne de blocs :
        - Présence et intégrité du bloc Genesis
        - Cohérence des hashs propres (détection de falsification)
        - Cohérence du chaînage (`previous_hash`)
        - Respect du consensus Proof of Work sur chaque bloc
        """
        target_chain = chain if chain is not None else self.chain

        if not target_chain:
            return False, "La chaîne est vide."

        genesis = target_chain[0]
        if genesis.index != 0 or genesis.previous_hash != "0" * 64:
            return False, "Le bloc Genesis (index 0) a une structure invalide."

        if genesis.hash != genesis.compute_hash():
            return False, "Le bloc Genesis (index 0) a été falsifié (hash incohérent)."

        if not genesis.hash.startswith(self.target_prefix):
            return False, "Le bloc Genesis ne respecte pas la difficulté PoW."

        for i in range(1, len(target_chain)):
            current_block = target_chain[i]
            prev_block = target_chain[i - 1]

            # 1. Vérification du hash propre du bloc précédent (au cas où il a été modifié)
            if prev_block.hash != prev_block.compute_hash():
                return (
                    False,
                    f"Bloc #{prev_block.index} falsifié : son contenu ne correspond plus à son hash.",
                )

            # 2. Vérification du bloc courant par rapport au bloc précédent
            valid, reason = self.is_valid_block(current_block, prev_block)
            if not valid:
                return False, f"Bloc #{current_block.index} invalide : {reason}"

        return True, "La chaîne est intègre et valide."

    def register_node(self, address: str) -> str:
        """
        Enregistre l'adresse d'un nœud pair dans le réseau (ex: 'http://127.0.0.1:5001').
        """
        if not address or not str(address).strip():
            raise ValueError("L'adresse du nœud ne peut pas être vide.")

        raw = str(address).strip()
        if "://" not in raw:
            raw = f"http://{raw}"

        parsed_url = urlparse(raw)
        if not parsed_url.netloc:
            raise ValueError(f"URL de nœud invalide : '{address}'.")

        normalized = f"{parsed_url.scheme}://{parsed_url.netloc}"
        self.nodes.add(normalized)
        return normalized

    def resolve_conflicts(self) -> tuple[bool, Dict[str, Any]]:
        """
        Algorithme de consensus réseau (règle de la chaîne valide la plus longue) :
        Interroge tous les nœuds pairs enregistrés et remplace la chaîne locale
        si une chaîne strictement plus longue et 100% valide est trouvée sur le réseau.
        """
        new_chain: Optional[List[Block]] = None
        max_length: int = len(self.chain)
        winning_node: Optional[str] = None
        checked_nodes: List[Dict[str, Any]] = []

        # Si la chaîne locale actuelle est corrompue, toute chaîne valide d'au moins la même taille peut la remplacer
        local_valid, _ = self.is_valid_chain(self.chain)
        if not local_valid:
            max_length = 0

        for node in self.nodes:
            try:
                response = requests.get(f"{node}/chain", timeout=3)
                if response.status_code == 200:
                    data = response.json()
                    length = int(data.get("length", 0))
                    raw_chain = data.get("chain", [])
                    candidate_chain = [Block.from_dict(b) for b in raw_chain]

                    is_valid, reason = self.is_valid_chain(candidate_chain)
                    checked_nodes.append(
                        {
                            "node": node,
                            "length": length,
                            "is_valid": is_valid,
                            "reason": reason,
                        }
                    )

                    if is_valid and length > max_length:
                        max_length = length
                        new_chain = candidate_chain
                        winning_node = node
                else:
                    checked_nodes.append(
                        {
                            "node": node,
                            "error": f"HTTP {response.status_code}",
                        }
                    )
            except requests.RequestException as exc:
                checked_nodes.append(
                    {
                        "node": node,
                        "error": str(exc),
                    }
                )

        if new_chain is not None:
            self.chain = new_chain
            self._backup_chain = None
            return True, {
                "replaced": True,
                "winning_node": winning_node,
                "new_length": len(self.chain),
                "checked_nodes": checked_nodes,
            }

        return False, {
            "replaced": False,
            "winning_node": None,
            "new_length": len(self.chain),
            "checked_nodes": checked_nodes,
        }

    def get_balances(self) -> Dict[str, float]:
        """
        Calcule le solde confirmé de chaque participant à partir de tous les blocs
        validés dans la chaîne.
        """
        balances: Dict[str, float] = {}
        system_senders = {"GENESIS", "0 (Récompense Réseau)"}

        for block in self.chain:
            for tx in block.transactions:
                sender = str(tx.get("sender", ""))
                recipient = str(tx.get("recipient", ""))
                amount = float(tx.get("amount", 0.0))

                if sender and sender not in system_senders:
                    balances[sender] = round(balances.get(sender, 0.0) - amount, 4)

                if recipient and recipient != "RESEAU":
                    balances[recipient] = round(balances.get(recipient, 0.0) + amount, 4)

        return balances

    def broadcast_transaction(self, transaction: Dict[str, Any]) -> List[str]:
        """
        Diffuse une nouvelle transaction à tous les nœuds pairs enregistrés
        pour qu'elle apparaisse dans leur Mempool respective.
        """
        notified: List[str] = []
        payload = {
            "sender": transaction["sender"],
            "recipient": transaction["recipient"],
            "amount": transaction["amount"],
            "broadcast": False,  # Évite les boucles de diffusion infinies
        }
        for node in list(self.nodes):
            try:
                res = requests.post(f"{node}/transactions/new", json=payload, timeout=1.5)
                if res.status_code == 201:
                    notified.append(node)
            except requests.RequestException:
                pass
        return notified

    def broadcast_block(self, block: Block) -> List[str]:
        """
        Diffuse un bloc fraîchement miné aux nœuds pairs.
        """
        notified: List[str] = []
        payload = block.to_dict()
        for node in list(self.nodes):
            try:
                res = requests.post(f"{node}/blocks/add", json=payload, timeout=1.5)
                if res.status_code == 201:
                    notified.append(node)
            except requests.RequestException:
                pass
        return notified

    # --- Méthodes utilitaires pour la démonstration de falsification ---

    def tamper_block(self, block_index: int, fake_amount: float = 999999.0) -> tuple[bool, str]:
        """
        Simule une attaque en modifiant frauduleusement une transaction d'un bloc existant
        sans recalculer toute la chaîne, afin de démontrer la détection de falsification.
        """
        if block_index < 0 or block_index >= len(self.chain):
            return False, f"Le bloc #{block_index} n'existe pas."

        if self._backup_chain is None:
            self._backup_chain = copy.deepcopy(self.chain)

        target_block = self.chain[block_index]
        if target_block.transactions:
            target_block.transactions[0]["amount"] = fake_amount
        else:
            target_block.transactions.append(
                {"sender": "HACKER", "recipient": "HACKER", "amount": fake_amount}
            )

        return (
            True,
            f"Le bloc #{block_index} a été modifié (montant forcé à {fake_amount}).",
        )

    def restore_tampered_chain(self) -> bool:
        """Restaure la chaîne originale après une démonstration de falsification."""
        if self._backup_chain is not None:
            self.chain = copy.deepcopy(self._backup_chain)
            self._backup_chain = None
            return True
        return False
