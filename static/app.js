/**
 * Blockchain Explorer — Front-End P2P & Multi-PC (TP ESGI M1)
 */

const txForm = document.getElementById("tx-form");
const senderSelect = document.getElementById("sender");
const recipientSelect = document.getElementById("recipient");
const mineBtn = document.getElementById("mine-btn");
const broadcastMineEl = document.getElementById("broadcast-mine");
const nodeForm = document.getElementById("node-form");
const resolveBtn = document.getElementById("resolve-btn");
const refreshBtn = document.getElementById("refresh-btn");
const tamperBtn = document.getElementById("tamper-btn");
const restoreBtn = document.getElementById("restore-btn");
const badConsensusBtn = document.getElementById("bad-consensus-btn");

const nodeIdEl = document.getElementById("node-id");
const pendingCountEl = document.getElementById("pending-count");
const peersCountEl = document.getElementById("peers-count");
const balancesListEl = document.getElementById("balances-list");
const pendingListEl = document.getElementById("pending-list");
const peersListEl = document.getElementById("peers-list");
const chainContainerEl = document.getElementById("chain-container");
const chainLengthEl = document.getElementById("chain-length");
const chainStatusBadgeEl = document.getElementById("chain-status-badge");
const statusTextEl = document.getElementById("status-text");
const validationDetailEl = document.getElementById("validation-detail");
const lastMineInfoEl = document.getElementById("last-mine-info");
const toastBannerEl = document.getElementById("toast-banner");

let currentNetworkMembers = [];

function showToast(message, type = "info") {
    toastBannerEl.textContent = message;
    toastBannerEl.className = `toast ${type}`;
    setTimeout(() => {
        toastBannerEl.classList.add("hidden");
    }, 5000);
}

function formatTime(ts) {
    return new Date(ts * 1000).toLocaleTimeString("fr-FR", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
    });
}

function formatHash(hashStr, prefix) {
    if (hashStr.startsWith(prefix)) {
        return `<span class="pow-highlight">${hashStr.slice(0, prefix.length)}</span>${hashStr.slice(prefix.length)}`;
    }
    return hashStr;
}

function updateMemberSelectors(members, localNodeId) {
    const prevSender = senderSelect.value || localNodeId;
    const prevRecipient = recipientSelect.value;

    currentNetworkMembers = members;

    // 1. Liste Émetteur : uniquement les membres du réseau
    senderSelect.innerHTML = "";
    members.forEach((member) => {
        const opt = document.createElement("option");
        opt.value = member;
        opt.textContent = member === localNodeId ? `${member} (Ce PC)` : member;
        if (member === prevSender) {
            opt.selected = true;
        }
        senderSelect.appendChild(opt);
    });

    // 2. Liste Destinataire : uniquement les membres du réseau différents de l'émetteur
    syncRecipientOptions(prevRecipient);
}

function syncRecipientOptions(preferredRecipient = "") {
    const selectedSender = senderSelect.value;
    const availableRecipients = currentNetworkMembers.filter((m) => m !== selectedSender);

    recipientSelect.innerHTML = "";
    if (availableRecipients.length === 0) {
        const opt = document.createElement("option");
        opt.value = "";
        opt.textContent = "Connectez d'abord un pair...";
        recipientSelect.appendChild(opt);
        recipientSelect.disabled = true;
        return;
    }

    recipientSelect.disabled = false;
    availableRecipients.forEach((member, idx) => {
        const opt = document.createElement("option");
        opt.value = member;
        opt.textContent = member;
        if (member === preferredRecipient || (!preferredRecipient && idx === 0)) {
            opt.selected = true;
        }
        recipientSelect.appendChild(opt);
    });
}

senderSelect.addEventListener("change", () => {
    syncRecipientOptions(recipientSelect.value);
});

async function fetchChainState() {
    try {
        const res = await fetch("/chain");
        const data = await res.json();
        renderDashboard(data);
    } catch {
        // Silencieux lors du rafraîchissement périodique
    }
}

function renderDashboard(data) {
    chainLengthEl.textContent = data.length;
    const pending = data.pending_transactions || [];
    const nodes = data.nodes || [];
    const balances = data.balances || {};
    const members = data.network_members || [data.node_id];

    updateMemberSelectors(members, data.node_id);

    pendingCountEl.textContent = pending.length;
    peersCountEl.textContent = nodes.length;
    validationDetailEl.textContent = data.validation_message;

    if (data.is_valid) {
        statusTextEl.textContent = "Chaîne Intègre";
        chainStatusBadgeEl.className = "status-chip valid";
    } else {
        statusTextEl.textContent = "Chaîne Altérée";
        chainStatusBadgeEl.className = "status-chip invalid";
    }

    // Soldes des participants
    balancesListEl.innerHTML = "";
    const entries = Object.entries(balances);
    if (entries.length === 0) {
        balancesListEl.innerHTML = `<span class="stat-sub">Aucun solde (minez un bloc)</span>`;
    } else {
        entries.forEach(([user, bal]) => {
            const pill = document.createElement("span");
            pill.className = "balance-pill";
            pill.innerHTML = `<span>${user}</span><strong>${bal}</strong>`;
            balancesListEl.appendChild(pill);
        });
    }

    // Mempool
    pendingListEl.innerHTML = "";
    if (pending.length === 0) {
        pendingListEl.innerHTML = `<li class="empty-state">Aucune transaction en attente</li>`;
    } else {
        pending.forEach((tx) => {
            const li = document.createElement("li");
            li.className = "tx-pill";
            li.innerHTML = `
                <div class="tx-route">
                    <strong>${tx.sender}</strong>
                    <span class="tx-arrow">→</span>
                    <strong>${tx.recipient}</strong>
                </div>
                <span class="tx-amount">+${tx.amount}</span>
            `;
            pendingListEl.appendChild(li);
        });
    }

    // Peers
    peersListEl.innerHTML = "";
    if (nodes.length === 0) {
        peersListEl.innerHTML = `<span class="stat-sub">Aucun pair connecté</span>`;
    } else {
        nodes.forEach((url) => {
            const chip = document.createElement("span");
            chip.className = "peer-chip";
            chip.textContent = url.replace("http://", "");
            peersListEl.appendChild(chip);
        });
    }

    // Blocks Explorer
    chainContainerEl.innerHTML = "";
    const prefix = data.target_prefix || "0000";

    data.chain.forEach((block) => {
        const isGenesis = block.index === 0;
        const isTampered = !data.is_valid && data.validation_message.includes(`#${block.index}`);
        const card = document.createElement("div");
        card.className = `block-card ${isGenesis ? "genesis" : "mined"} ${isTampered ? "tampered" : ""}`;

        const txRows = (block.transactions || [])
            .map((tx) => {
                const isReward = String(tx.sender).startsWith("0 ");
                return `
                    <div class="block-tx-row">
                        <span>${isReward ? `<span class="reward-label">★ Récompense</span>` : `${tx.sender}`} → <strong>${tx.recipient}</strong></span>
                        <span class="tx-amount">${tx.amount}</span>
                    </div>
                `;
            })
            .join("");

        card.innerHTML = `
            <div class="block-card-head">
                <div class="block-badge">
                    <span>Bloc #${block.index}</span>
                    ${isGenesis ? `<span class="genesis-tag">Genesis</span>` : ""}
                </div>
                <div class="block-meta-right">
                    <span class="nonce-tag">Nonce ${block.nonce}</span>
                    <span>${formatTime(block.timestamp)}</span>
                </div>
            </div>

            <div class="hash-box">
                <div class="hash-line" title="${block.hash}">
                    <span class="hash-tag">HASH</span>
                    <span class="hash-val">${formatHash(block.hash, prefix)}</span>
                </div>
                <div class="hash-line" title="${block.previous_hash}">
                    <span class="hash-tag">PRÉC</span>
                    <span class="hash-val">${block.previous_hash}</span>
                </div>
            </div>

            <div class="block-tx-list">
                ${txRows}
            </div>
        `;

        chainContainerEl.appendChild(card);
    });
}

txForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const sender = senderSelect.value;
    const recipient = recipientSelect.value;
    const amount = parseFloat(document.getElementById("amount").value);

    if (!recipient) {
        showToast("Connectez d'abord un nœud pair dans le réseau.", "error");
        return;
    }

    const res = await fetch("/transactions/new", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sender, recipient, amount, broadcast: true }),
    });
    const data = await res.json();
    if (!res.ok) {
        showToast(data.error || "Erreur", "error");
        return;
    }
    const peerCount = (data.broadcasted_to || []).length;
    const extra = peerCount > 0 ? ` (diffusée à ${peerCount} PC pairs)` : "";
    showToast(`${data.message}${extra}`, "success");
    document.getElementById("amount").value = "";
    fetchChainState();
});

mineBtn.addEventListener("click", async () => {
    const nodeName = nodeIdEl.textContent;
    const shouldBroadcast = broadcastMineEl && broadcastMineEl.checked ? "1" : "0";
    mineBtn.disabled = true;
    mineBtn.innerHTML = `<span>Minage PoW...</span>`;

    try {
        const res = await fetch(`/mine?broadcast=${shouldBroadcast}`);
        const data = await res.json();
        if (!res.ok) {
            showToast(data.error || "Erreur de minage", "error");
        } else {
            lastMineInfoEl.textContent = `${data.mining_time_ms} ms · Nonce ${data.block.nonce}`;
            const peerCount = (data.broadcasted_to || []).length;
            const extra = peerCount > 0 ? ` · propagé à ${peerCount} PC` : "";
            showToast(`Bloc #${data.block.index} miné (${data.mining_time_ms} ms)${extra}`, "success");
            fetchChainState();
        }
    } finally {
        mineBtn.disabled = false;
        mineBtn.innerHTML = `<span>Miner un bloc (+1.00 ${nodeName})</span>`;
    }
});

nodeForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const peerUrl = document.getElementById("peer-url").value.trim();
    const res = await fetch("/nodes/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nodes: [peerUrl] }),
    });
    const data = await res.json();
    if (!res.ok) {
        showToast(data.error || "Erreur", "error");
        return;
    }
    showToast(data.message, "success");
    nodeForm.reset();
    fetchChainState();
});

resolveBtn.addEventListener("click", async () => {
    const res = await fetch("/nodes/resolve");
    const data = await res.json();
    showToast(data.message, data.replaced ? "success" : "info");
    fetchChainState();
});

tamperBtn.addEventListener("click", async () => {
    const res = await fetch("/demo/tamper", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ fake_amount: 999999 }),
    });
    const data = await res.json();
    showToast(data.validation_message, "error");
    fetchChainState();
});

restoreBtn.addEventListener("click", async () => {
    const res = await fetch("/demo/restore", { method: "POST" });
    const data = await res.json();
    showToast(data.message, "success");
    fetchChainState();
});

badConsensusBtn.addEventListener("click", async () => {
    const res = await fetch("/blocks/add", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            transactions: [{ sender: "Pirate", recipient: "Pirate", amount: 500 }],
            nonce: 0,
            hash: "1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        }),
    });
    const data = await res.json();
    showToast(data.message, "info");
});

refreshBtn.addEventListener("click", fetchChainState);

fetchChainState();
setInterval(fetchChainState, 3000);
