"""
Script de démonstration complète et automatisée des 5 preuves exigées par le TP :
1. Création d'un bloc et vérification du chaînage (hash précédent cohérent)
2. Ajout de transactions puis minage d'un bloc les contenant
3. Détection d'une chaîne falsifiée (bloc modifié -> chaîne invalide)
4. Résolution de conflits : deux nœuds en désaccord convergent vers la même chaîne
5. Validité du consensus : un bloc au consensus invalide est rejeté

Ce script démarre également deux nœuds Flask réels en arrière-plan pour prouver
le fonctionnement de l'API REST et du réseau multi-nœuds par HTTP.
"""

from __future__ import annotations

import threading
import time
from werkzeug.serving import make_server

import requests

from app import create_app
from blockchain import Block, Blockchain


class ServerThread(threading.Thread):
    """Exécute un serveur Flask dans un thread dédié pour la démo multi-nœuds."""

    def __init__(self, app, port: int) -> None:
        super().__init__(daemon=True)
        self.server = make_server("127.0.0.1", port, app, threaded=True)
        self.ctx = app.app_context()
        self.ctx.push()

    def run(self) -> None:
        self.server.serve_forever()

    def shutdown(self) -> None:
        self.server.shutdown()


def print_banner(title: str) -> None:
    print("\n" + "=" * 78)
    print(f"🔹 {title}")
    print("=" * 78)


def run_demonstration() -> None:
    print("🚀 DÉMONSTRATION OFFICIELLE — TP BLOCKCHAIN DE ZÉRO (MASTER 1 ESGI)")

    bc = Blockchain(difficulty=4)

    # -------------------------------------------------------------------------
    # PREUVE 1 : Création d'un bloc et vérification du chaînage
    # -------------------------------------------------------------------------
    print_banner("PREUVE 1 : Création d'un bloc et vérification du chaînage")
    genesis = bc.chain[0]
    print(f"• Bloc Genesis (#0) créé :")
    print(f"  - Hash propre   : {genesis.hash}")
    print(f"  - Previous hash : {genesis.previous_hash}")
    print(f"  - Nonce PoW     : {genesis.nonce}")

    block_1 = bc.mine_pending_transactions(miner_address="noeud-demo")
    print(f"\n• Nouveau Bloc (#1) miné :")
    print(f"  - Hash propre   : {block_1.hash}")
    print(f"  - Previous hash : {block_1.previous_hash}")
    print(f"  - Nonce PoW     : {block_1.nonce}")

    assert block_1.previous_hash == genesis.hash, "Erreur : le chaînage est incohérent !"
    is_valid, msg = bc.is_valid_chain()
    assert is_valid, f"Erreur : {msg}"
    print(f"✅ VÉRIFIÉ : block_1.previous_hash == genesis.hash ({block_1.previous_hash[:16]}...)")
    print(f"✅ Statut de la chaîne : {msg}")

    # -------------------------------------------------------------------------
    # PREUVE 2 : Ajout de transactions puis minage d'un bloc les contenant
    # -------------------------------------------------------------------------
    print_banner("PREUVE 2 : Ajout de transactions en attente puis minage d'un bloc")
    target_idx_1 = bc.add_transaction(sender="Alice", recipient="Bob", amount=50.0)
    target_idx_2 = bc.add_transaction(sender="Bob", recipient="Charlie", amount=15.5)
    print(f"• 2 transactions ajoutées en mempool (prévues pour le bloc #{target_idx_1}) :")
    for tx in bc.pending_transactions:
        print(f"  - {tx['sender']} -> {tx['recipient']} : {tx['amount']} BTC")

    block_2 = bc.mine_pending_transactions(miner_address="noeud-demo")
    print(f"\n• Bloc #{block_2.index} miné avec hash : {block_2.hash} (nonce={block_2.nonce})")
    print("• Transactions incluses dans le Bloc #2 :")
    for tx in block_2.transactions:
        print(f"  - {tx['sender']} -> {tx['recipient']} : {tx['amount']} BTC")

    assert len(bc.pending_transactions) == 0, "La mempool devrait être vide après minage."
    assert any(
        tx["sender"] == "Alice" and tx["recipient"] == "Bob" and tx["amount"] == 50.0
        for tx in block_2.transactions
    )
    print("✅ VÉRIFIÉ : Les transactions ont bien été inscrites dans le bloc #2 et la mempool est vidée.")

    # -------------------------------------------------------------------------
    # PREUVE 3 : Détection d'une chaîne falsifiée (bloc modifié -> chaîne invalide)
    # -------------------------------------------------------------------------
    print_banner("PREUVE 3 : Détection d'une chaîne falsifiée (Immuabilité)")
    print("• État avant attaque :", bc.is_valid_chain())
    print("• Attaque : modification frauduleuse du montant d'Alice dans le Bloc #2 (50.0 -> 999999.0)...")
    bc.tamper_block(block_index=2, fake_amount=999999.0)

    is_valid_after_attack, reason_attack = bc.is_valid_chain()
    print(f"• Résultat de is_valid_chain() après falsification : {is_valid_after_attack}")
    print(f"• Raison détectée : {reason_attack}")
    assert not is_valid_after_attack, "La falsification aurait dû invalider la chaîne !"
    print("✅ VÉRIFIÉ : La chaîne falsifiée est immédiatement détectée et rejetée.")

    bc.restore_tampered_chain()
    assert bc.is_valid_chain()[0], "La chaîne restaurée doit être valide."
    print("• Chaîne restaurée à son état valide initial.")

    # -------------------------------------------------------------------------
    # PREUVE 4 : Validité du consensus (un bloc au consensus invalide est rejeté)
    # -------------------------------------------------------------------------
    print_banner("PREUVE 4 : Validité du consensus (Rejet d'un bloc sans Proof of Work)")
    fake_block = Block(
        index=bc.last_block.index + 1,
        transactions=[{"sender": "Attaquant", "recipient": "Attaquant", "amount": 1000.0}],
        previous_hash=bc.last_block.hash,
        nonce=0,  # Aucun Proof of Work effectué
    )
    # Si par chance extrême nonce=0 commence par 0000, on force un hash invalide
    if fake_block.hash.startswith(bc.target_prefix):
        fake_block.nonce = 1
        fake_block.hash = fake_block.compute_hash()

    print(f"• Tentative d'ajout d'un bloc non miné (hash = {fake_block.hash[:20]}..., ne commence pas par '{bc.target_prefix}')")
    accepted, reject_reason = bc.add_block(fake_block)
    print(f"• Résultat add_block() : accepté={accepted} | motif : {reject_reason}")
    assert not accepted, "Un bloc au consensus invalide ne doit jamais être accepté !"
    print("✅ VÉRIFIÉ : Le bloc au consensus invalide est rejeté.")

    # -------------------------------------------------------------------------
    # PREUVE 5 : Résolution de conflits entre 2 nœuds Flask réels en désaccord
    # -------------------------------------------------------------------------
    print_banner("PREUVE 5 : Réseau Multi-Nœuds & Résolution de conflits (API Flask)")
    port_a, port_b = 5051, 5052
    url_a = f"http://127.0.0.1:{port_a}"
    url_b = f"http://127.0.0.1:{port_b}"

    app_a = create_app(difficulty=4, node_id="noeud-A")
    app_b = create_app(difficulty=4, node_id="noeud-B")

    srv_a = ServerThread(app_a, port_a)
    srv_b = ServerThread(app_b, port_b)
    srv_a.start()
    srv_b.start()
    time.sleep(0.3)

    try:
        # Enregistrement mutuel des pairs via POST /nodes/register
        requests.post(f"{url_a}/nodes/register", json={"nodes": [url_b]}, timeout=3)
        requests.post(f"{url_b}/nodes/register", json={"nodes": [url_a]}, timeout=3)
        print(f"• Nœud A ({url_a}) et Nœud B ({url_b}) démarrés et interconnectés.")

        # Création d'un désaccord : Nœud A mine 2 blocs, Nœud B n'en mine qu'un seul
        requests.post(
            f"{url_a}/transactions/new",
            json={"sender": "noeud-A", "recipient": "noeud-B", "amount": 10},
            timeout=3,
        )
        requests.get(f"{url_a}/mine", timeout=10)
        requests.get(f"{url_a}/mine", timeout=10)

        requests.post(
            f"{url_b}/transactions/new",
            json={"sender": "noeud-B", "recipient": "noeud-A", "amount": 5},
            timeout=3,
        )
        requests.get(f"{url_b}/mine", timeout=10)

        chain_a_before = requests.get(f"{url_a}/chain", timeout=3).json()
        chain_b_before = requests.get(f"{url_b}/chain", timeout=3).json()
        print(
            f"• Avant résolution : Nœud A possède {chain_a_before['length']} blocs | "
            f"Nœud B possède {chain_b_before['length']} blocs (DÉSACCORD)."
        )

        # Résolution de conflits sur le Nœud B via GET /nodes/resolve
        resolve_res = requests.get(f"{url_b}/nodes/resolve", timeout=5).json()
        print(f"• Appel GET {url_b}/nodes/resolve -> {resolve_res['message']}")

        chain_a_after = requests.get(f"{url_a}/chain", timeout=3).json()
        chain_b_after = requests.get(f"{url_b}/chain", timeout=3).json()

        assert resolve_res["replaced"] is True
        assert chain_b_after["length"] == chain_a_after["length"] == 3
        assert chain_b_after["chain"][-1]["hash"] == chain_a_after["chain"][-1]["hash"]
        print(
            f"✅ VÉRIFIÉ : Nœud A et Nœud B ont convergé vers la même chaîne de longueur "
            f"{chain_b_after['length']} (hash final : {chain_b_after['chain'][-1]['hash'][:20]}...)."
        )
    finally:
        srv_a.shutdown()
        srv_b.shutdown()

    print("\n" + "=" * 78)
    print("🎉 TOUTES LES 5 DÉMONSTRATIONS DU TP ONT RÉUSSI AVEC SUCCÈS !")
    print("=" * 78)


if __name__ == "__main__":
    run_demonstration()
