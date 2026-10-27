"""
Serveur Flask exposant l'API REST de la Blockchain et le Dashboard Web.
Supporte le déploiement multi-conteneurs Docker et la communication entre PC sur un réseau local.
TP — Blockchain de Zéro (Master 1 — ESGI)
"""

from __future__ import annotations

import argparse
import os
import socket
import time
from uuid import uuid4

from flask import Flask, jsonify, render_template, request

from blockchain import Block, Blockchain


def get_local_ip() -> str:
    """Détecte l'adresse IP locale (LAN) de la machine ou du conteneur."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def create_app(
    difficulty: int = 4,
    node_id: str | None = None,
    initial_peers: list[str] | None = None,
    port: int = 5000,
) -> Flask:
    """Crée et configure l'application Flask pour un nœud de la blockchain."""
    app = Flask(__name__)

    node_identifier = node_id or os.environ.get("NODE_ID") or f"node-{str(uuid4()).replace('-', '')[:6]}"
    blockchain = Blockchain(difficulty=difficulty, node_id=node_identifier)
    local_ip = get_local_ip()

    # Pré-enregistrement des pairs fournis par variable d'environnement PEERS ou argument
    env_peers = os.environ.get("PEERS", "")
    peer_candidates = list(initial_peers or [])
    if env_peers.strip():
        peer_candidates.extend([p.strip() for p in env_peers.split(",") if p.strip()])

    for peer in peer_candidates:
        try:
            blockchain.register_node(peer)
        except ValueError:
            pass

    app.config["BLOCKCHAIN"] = blockchain
    app.config["NODE_ID"] = node_identifier
    app.config["TEMPLATES_AUTO_RELOAD"] = True

    @app.route("/", methods=["GET"])
    def dashboard():
        """Affiche le Dashboard Web interactif."""
        return render_template(
            "index.html",
            node_id=node_identifier,
            difficulty=blockchain.difficulty,
            lan_url=f"http://{local_ip}:{port}",
        )

    @app.route("/chain", methods=["GET"])
    def get_chain():
        """
        GET /chain
        Retourne la chaîne complète, sa longueur, les transactions en attente,
        les soldes des participants ainsi que l'état de validité de la chaîne.
        """
        is_valid, validation_message = blockchain.is_valid_chain()
        response = {
            "node_id": node_identifier,
            "lan_url": f"http://{local_ip}:{port}",
            "difficulty": blockchain.difficulty,
            "target_prefix": blockchain.target_prefix,
            "length": len(blockchain.chain),
            "is_valid": is_valid,
            "validation_message": validation_message,
            "chain": [block.to_dict() for block in blockchain.chain],
            "pending_transactions": blockchain.pending_transactions,
            "balances": blockchain.get_balances(),
            "nodes": sorted(list(blockchain.nodes)),
            "network_members": blockchain.get_network_members(),
        }
        return jsonify(response), 200

    @app.route("/transactions/new", methods=["POST"])
    def new_transaction():
        """
        POST /transactions/new
        Ajoute une transaction en attente (sender, recipient, amount)
        et la diffuse aux nœuds pairs si `broadcast` est actif (par défaut).
        """
        values = request.get_json(silent=True)
        if not values:
            return jsonify({"error": "Corps JSON invalide ou manquant."}), 400

        required_fields = ["sender", "recipient", "amount"]
        missing = [field for field in required_fields if field not in values]
        if missing:
            return (
                jsonify({"error": f"Champs manquants : {', '.join(missing)}"}),
                400,
            )

        try:
            allowed = set(blockchain.get_network_members())
            block_index = blockchain.add_transaction(
                sender=values["sender"],
                recipient=values["recipient"],
                amount=values["amount"],
                allowed_members=allowed,
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        created_tx = blockchain.pending_transactions[-1]
        should_broadcast = bool(values.get("broadcast", True))
        notified_peers = []
        if should_broadcast and blockchain.nodes:
            notified_peers = blockchain.broadcast_transaction(created_tx)

        response = {
            "message": f"Transaction ajoutée pour le bloc #{block_index}.",
            "block_index": block_index,
            "transaction": created_tx,
            "pending_count": len(blockchain.pending_transactions),
            "broadcasted_to": notified_peers,
        }
        return jsonify(response), 201

    @app.route("/mine", methods=["GET", "POST"])
    def mine():
        """
        GET /mine
        Exécute le Proof of Work pour forger un nouveau bloc contenant les transactions
        en attente ainsi qu'une récompense de minage pour ce nœud.
        """
        is_valid, reason = blockchain.is_valid_chain()
        if not is_valid:
            return (
                jsonify(
                    {
                        "error": f"Minage refusé : la chaîne locale est invalide ({reason}).",
                    }
                ),
                400,
            )

        start_time = time.perf_counter()
        mined_block = blockchain.mine_pending_transactions(miner_address=node_identifier)
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Si ?broadcast=1 est passé par le Dashboard, diffuse le bloc miné aux pairs
        broadcast_param = request.args.get("broadcast", "0")
        notified_peers = []
        if broadcast_param == "1" and blockchain.nodes:
            notified_peers = blockchain.broadcast_block(mined_block)

        response = {
            "message": f"Bloc #{mined_block.index} miné avec succès !",
            "block": mined_block.to_dict(),
            "mining_time_ms": elapsed_ms,
            "chain_length": len(blockchain.chain),
            "broadcasted_to": notified_peers,
        }
        return jsonify(response), 200

    @app.route("/nodes", methods=["GET"])
    def list_nodes():
        """GET /nodes : Retourne la liste des nœuds pairs enregistrés."""
        return (
            jsonify(
                {
                    "node_id": node_identifier,
                    "nodes": sorted(list(blockchain.nodes)),
                    "total_nodes": len(blockchain.nodes),
                }
            ),
            200,
        )

    @app.route("/nodes/register", methods=["POST"])
    def register_nodes():
        """
        POST /nodes/register
        Enregistre une liste de nœuds pairs sous la forme {"nodes": ["http://127.0.0.1:5001"]}.
        """
        values = request.get_json(silent=True)
        if not values or "nodes" not in values:
            return (
                jsonify({"error": "Veuillez fournir une liste de nœuds dans le champ 'nodes'."}),
                400,
            )

        raw_nodes = values.get("nodes")
        if not isinstance(raw_nodes, list) or not raw_nodes:
            return (
                jsonify({"error": "Le champ 'nodes' doit être une liste non vide d'URLs."}),
                400,
            )

        registered = []
        try:
            for node_url in raw_nodes:
                normalized = blockchain.register_node(node_url)
                registered.append(normalized)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        return (
            jsonify(
                {
                    "message": "Nœud(s) pair(s) connecté(s) avec succès.",
                    "registered": registered,
                    "total_nodes": sorted(list(blockchain.nodes)),
                }
            ),
            201,
        )

    @app.route("/nodes/resolve", methods=["GET", "POST"])
    def consensus():
        """
        GET /nodes/resolve
        Résout les conflits entre nœuds en adoptant la chaîne valide la plus longue.
        """
        replaced, details = blockchain.resolve_conflicts()
        if replaced:
            message = (
                f"Conflit résolu : chaîne synchronisée depuis "
                f"{details['winning_node']} (longueur {details['new_length']})."
            )
        else:
            message = "Notre chaîne fait déjà autorité sur le réseau."

        return (
            jsonify(
                {
                    "message": message,
                    "replaced": replaced,
                    "details": details,
                    "chain": [block.to_dict() for block in blockchain.chain],
                    "length": len(blockchain.chain),
                }
            ),
            200,
        )

    @app.route("/validate", methods=["GET"])
    def validate_chain():
        """GET /validate : Vérifie si la chaîne locale est intègre et valide."""
        is_valid, message = blockchain.is_valid_chain()
        return (
            jsonify(
                {
                    "is_valid": is_valid,
                    "message": message,
                    "length": len(blockchain.chain),
                }
            ),
            200,
        )

    @app.route("/blocks/add", methods=["POST"])
    def add_external_block():
        """
        POST /blocks/add
        Tente d'ajouter un bloc fourni manuellement ou reçu d'un pair P2P.
        Rejette tout bloc dont le chaînage ou le consensus PoW est invalide.
        """
        values = request.get_json(silent=True)
        if not values:
            return jsonify({"error": "Corps JSON invalide."}), 400

        try:
            candidate_block = Block(
                index=int(values.get("index", blockchain.last_block.index + 1)),
                transactions=list(values.get("transactions", [])),
                previous_hash=str(values.get("previous_hash", blockchain.last_block.hash)),
                timestamp=float(values.get("timestamp", time.time())),
                nonce=int(values.get("nonce", 0)),
                block_hash=values.get("hash"),
            )
        except (TypeError, ValueError) as exc:
            return jsonify({"error": f"Format de bloc invalide : {exc}"}), 400

        accepted, reason = blockchain.add_block(candidate_block)
        if not accepted:
            return (
                jsonify(
                    {
                        "accepted": False,
                        "message": f"Bloc rejeté par le consensus : {reason}",
                        "candidate_block": candidate_block.to_dict(),
                    }
                ),
                400,
            )

        return (
            jsonify(
                {
                    "accepted": True,
                    "message": "Bloc externe validé et ajouté à la chaîne.",
                    "block": candidate_block.to_dict(),
                }
            ),
            201,
        )

    @app.route("/demo/tamper", methods=["POST"])
    def demo_tamper():
        """POST /demo/tamper : Falsifie un bloc existant pour démontrer la détection."""
        values = request.get_json(silent=True) or {}
        default_index = 1 if len(blockchain.chain) > 1 else 0
        block_index = int(values.get("block_index", default_index))
        fake_amount = float(values.get("fake_amount", 999999.0))

        ok, msg = blockchain.tamper_block(block_index=block_index, fake_amount=fake_amount)
        if not ok:
            return jsonify({"error": msg}), 400

        is_valid, validation_message = blockchain.is_valid_chain()
        return (
            jsonify(
                {
                    "message": msg,
                    "is_valid": is_valid,
                    "validation_message": validation_message,
                }
            ),
            200,
        )

    @app.route("/demo/restore", methods=["POST"])
    def demo_restore():
        """POST /demo/restore : Restaure la chaîne originale après falsification."""
        restored = blockchain.restore_tampered_chain()
        is_valid, validation_message = blockchain.is_valid_chain()
        return (
            jsonify(
                {
                    "restored": restored,
                    "message": (
                        "Chaîne originale restaurée."
                        if restored
                        else "Aucune sauvegarde à restaurer."
                    ),
                    "is_valid": is_valid,
                    "validation_message": validation_message,
                }
            ),
            200,
        )

    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Serveur Nœud Blockchain (TP ESGI M1)")
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=int(os.environ.get("PORT", "5000")),
        help="Port d'écoute du serveur Flask (défaut: 5000)",
    )
    parser.add_argument(
        "-d",
        "--difficulty",
        type=int,
        default=int(os.environ.get("DIFFICULTY", "4")),
        help="Difficulté du Proof of Work (défaut: 4)",
    )
    parser.add_argument(
        "--node-id",
        type=str,
        default=os.environ.get("NODE_ID"),
        help="Identifiant personnalisé du nœud (ex: pc-alice)",
    )
    args = parser.parse_args()

    custom_id = args.node_id or f"node-{args.port}"
    flask_app = create_app(
        difficulty=args.difficulty,
        node_id=custom_id,
        port=args.port,
    )
    print(f"🚀 Démarrage du nœud '{custom_id}' sur http://0.0.0.0:{args.port} (PoW difficulté={args.difficulty})")
    flask_app.run(host="0.0.0.0", port=args.port, debug=False)
