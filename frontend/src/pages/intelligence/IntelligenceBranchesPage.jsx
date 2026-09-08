import {
  ArrowRightLeft,
  Boxes,
  Building2,
  CircleDollarSign,
  LoaderCircle,
  PackagePlus,
  RefreshCw,
  ShieldCheck,
  TrendingUp,
  Users,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import Button from "../../components/ui/Button";
import Modal from "../../components/ui/Modal";
import { useStore } from "../../context/StoreContext";
import { apiRequest } from "../../services/api";
import { formatCurrency } from "../../utils/formatters";


const EMPTY_BRANCH_FORM = {
  name: "",
  code: "",
  location: "",
  phone: "",
};

const EMPTY_TRANSFER_FORM = {
  sourceBranchId: "",
  destinationBranchId: "",
  productId: "",
  quantity: "1",
  reason: "",
};

function numberValue(value) {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function dateTimeLabel(value) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-GH", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export default function IntelligenceBranchesPage() {
  const {
    business,
    branch,
    branches,
    activeBranchId,
    switchBranch,
    loadBranches,
    loadInventory,
    team,
  } = useStore();
  const [intelligence, setIntelligence] = useState(null);
  const [transfers, setTransfers] = useState([]);
  const [sourceInventory, setSourceInventory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [notice, setNotice] = useState(null);
  const [branchForm, setBranchForm] = useState(EMPTY_BRANCH_FORM);
  const [transferForm, setTransferForm] = useState(EMPTY_TRANSFER_FORM);
  const [pendingTransfer, setPendingTransfer] = useState(null);
  const [transferConfirmError, setTransferConfirmError] = useState("");
  const [accessBranchId, setAccessBranchId] = useState("");
  const [membershipIds, setMembershipIds] = useState([]);

  const loadWorkspace = useCallback(async () => {
    if (!business.id) return;
    setLoading(true);
    setNotice(null);

    try {
      const [intelligenceData, transferData] = await Promise.all([
        apiRequest(`/businesses/${business.id}/intelligence/branches/`),
        apiRequest(`/businesses/${business.id}/branch-transfers/`),
      ]);
      setIntelligence(intelligenceData);
      setTransfers(Array.isArray(transferData) ? transferData : []);
    } catch (error) {
      setNotice({ tone: "error", text: error.message });
    } finally {
      setLoading(false);
    }
  }, [business.id]);

  useEffect(() => {
    loadWorkspace();
  }, [loadWorkspace]);

  useEffect(() => {
    if (!business.id || !transferForm.sourceBranchId) {
      setSourceInventory([]);
      return;
    }

    apiRequest(
      `/businesses/${business.id}/branch-inventory/?branchId=${encodeURIComponent(
        transferForm.sourceBranchId,
      )}`,
    )
      .then((records) => setSourceInventory(Array.isArray(records) ? records : []))
      .catch((error) => {
        setSourceInventory([]);
        setNotice({ tone: "error", text: error.message });
      });
  }, [business.id, transferForm.sourceBranchId]);

  const consolidated = intelligence?.consolidated ?? {};
  const branchRows = intelligence?.branches ?? [];
  const suggestions = intelligence?.transferSuggestions ?? [];
  const activeTeam = useMemo(
    () => team.filter((member) => member.status === "active"),
    [team],
  );

  async function refreshAll(message = "Multi-branch data refreshed.") {
    await Promise.all([loadBranches(business.id, activeBranchId), loadWorkspace()]);
    if (activeBranchId) {
      await loadInventory(business.id, activeBranchId);
    }
    setNotice({ tone: "success", text: message });
  }

  async function createBranch(event) {
    event.preventDefault();
    setActionLoading(true);
    setNotice(null);

    try {
      const created = await apiRequest(`/businesses/${business.id}/branches/`, {
        method: "POST",
        body: JSON.stringify({
          ...branchForm,
          code: branchForm.code.trim().toUpperCase(),
        }),
      });
      setBranchForm(EMPTY_BRANCH_FORM);
      await loadBranches(business.id, created.id);
      await loadWorkspace();
      await loadInventory(business.id, created.id);
      setNotice({
        tone: "success",
        text: `${created.name} was created. Its inventory starts at zero until stock is transferred or received there.`,
      });
    } catch (error) {
      setNotice({ tone: "error", text: error.message });
    } finally {
      setActionLoading(false);
    }
  }

  // Opens StockFlow's branded confirmation instead of a browser-native dialog.
  function createTransfer(event) {
    event.preventDefault();
    const quantity = Number(transferForm.quantity);
    const product = sourceInventory.find(
      (item) => String(item.productId) === String(transferForm.productId),
    );
    const source = branches.find(
      (item) => String(item.id) === String(transferForm.sourceBranchId),
    );
    const destination = branches.find(
      (item) => String(item.id) === String(transferForm.destinationBranchId),
    );

    if (!product || !source || !destination || !Number.isFinite(quantity) || quantity <= 0) {
      setNotice({ tone: "error", text: "Choose valid branches, product and quantity." });
      return;
    }

    if (quantity > Number(product.availableStock ?? 0)) {
      setNotice({
        tone: "error",
        text: `Only ${product.availableStock} ${product.unit}(s) are available to transfer.`,
      });
      return;
    }

    setTransferConfirmError("");
    setPendingTransfer({
      sourceBranchId: source.id,
      sourceBranchName: source.name,
      destinationBranchId: destination.id,
      destinationBranchName: destination.name,
      productId: product.productId,
      productName: product.productName,
      unit: product.unit,
      quantity,
      reason: transferForm.reason.trim(),
    });
  }

  async function confirmTransfer() {
    if (!pendingTransfer || actionLoading) return;

    setActionLoading(true);
    setTransferConfirmError("");
    setNotice(null);

    try {
      await apiRequest(`/businesses/${business.id}/branch-transfers/`, {
        method: "POST",
        body: JSON.stringify({
          sourceBranchId: pendingTransfer.sourceBranchId,
          destinationBranchId: pendingTransfer.destinationBranchId,
          reason: pendingTransfer.reason,
          items: [
            {
              productId: pendingTransfer.productId,
              quantity: pendingTransfer.quantity,
            },
          ],
        }),
      });
      setPendingTransfer(null);
      setTransferForm(EMPTY_TRANSFER_FORM);
      setSourceInventory([]);
      await refreshAll("Branch transfer completed and both branch balances were reconciled.");
    } catch (error) {
      setTransferConfirmError(error.message);
    } finally {
      setActionLoading(false);
    }
  }

  function prepareSuggestion(suggestion) {
    setTransferForm({
      sourceBranchId: suggestion.sourceBranchId,
      destinationBranchId: suggestion.destinationBranchId,
      productId: suggestion.productId,
      quantity: String(suggestion.suggestedQuantity),
      reason: suggestion.reason,
    });
    setNotice({
      tone: "info",
      text: "Suggestion prepared only. Review the transfer and confirm it yourself before stock changes.",
    });
  }

  async function openBranchAccess(branchRecord) {
    setAccessBranchId(branchRecord.id);
    setMembershipIds(
      Array.isArray(branchRecord.assignedMemberIds)
        ? branchRecord.assignedMemberIds.map(String)
        : [],
    );
  }

  function toggleMembership(membershipId) {
    setMembershipIds((current) =>
      current.includes(String(membershipId))
        ? current.filter((id) => id !== String(membershipId))
        : [...current, String(membershipId)],
    );
  }

  async function saveBranchAccess() {
    if (!accessBranchId) return;
    setActionLoading(true);
    setNotice(null);
    try {
      await apiRequest(
        `/businesses/${business.id}/branches/${accessBranchId}/members/`,
        {
          method: "PUT",
          body: JSON.stringify({ membershipIds }),
        },
      );
      await loadBranches(business.id, activeBranchId);
      setAccessBranchId("");
      setMembershipIds([]);
      setNotice({ tone: "success", text: "Branch staff access updated." });
    } catch (error) {
      setNotice({ tone: "error", text: error.message });
    } finally {
      setActionLoading(false);
    }
  }

  return (
    <div className="intelligence-page intelligence-branches-page">
      <section className="intelligence-page-hero">
        <div>
          <span className="intelligence-eyebrow">
            <Building2 size={14} /> Multi-branch control
          </span>
          <h2>See every branch without losing the company-wide truth.</h2>
          <p>
            Compare the last 30 days of revenue, gross profit, inventory and debt.
            Transfers move stock between locations only; they never create or remove
            company inventory.
          </p>
          <div className="intelligence-page-meta">
            <span>{business.name}</span>
            <span>•</span>
            <span>Working branch: {branch?.name || "Loading..."}</span>
            <span>•</span>
            <span>Django-calculated</span>
          </div>
        </div>
        <button
          type="button"
          className="intelligence-primary-action"
          onClick={() => refreshAll()}
          disabled={loading || actionLoading}
        >
          <RefreshCw size={16} /> Refresh
        </button>
      </section>

      {notice ? (
        <div className={`intelligence-branch-notice ${notice.tone}`}>
          {notice.text}
        </div>
      ) : null}

      {loading ? (
        <section className="intelligence-panel intelligence-branch-loading">
          <LoaderCircle size={20} /> Loading verified branch intelligence...
        </section>
      ) : (
        <>
          <section className="intelligence-metric-grid">
            <article className="intelligence-metric-card intelligence-metric-green">
              <span className="intelligence-metric-icon"><CircleDollarSign size={19} /></span>
              <div><span>30-day revenue</span><strong>{formatCurrency(numberValue(consolidated.revenue))}</strong><small>{consolidated.salesCount || 0} recognized sales</small></div>
            </article>
            <article className="intelligence-metric-card intelligence-metric-purple">
              <span className="intelligence-metric-icon"><TrendingUp size={19} /></span>
              <div><span>Gross profit</span><strong>{formatCurrency(numberValue(consolidated.grossProfit))}</strong><small>{numberValue(consolidated.profitMargin).toFixed(2)}% margin</small></div>
            </article>
            <article className="intelligence-metric-card intelligence-metric-amber">
              <span className="intelligence-metric-icon"><Boxes size={19} /></span>
              <div><span>Available stock</span><strong>{consolidated.availableStockUnits || 0}</strong><small>{consolidated.branchCount || 0} active branch(es)</small></div>
            </article>
          </section>

          <section className="intelligence-panel">
            <div className="intelligence-panel-heading">
              <div><span>Branch ranking</span><h3>Performance and risk by location</h3><small>Revenue and profit use immutable historical sale-item cost snapshots.</small></div>
            </div>
            <div className="intelligence-branch-table-wrap">
              <table>
                <thead><tr><th>Branch</th><th>Revenue</th><th>Gross profit</th><th>Available stock</th><th>Low / out</th><th>Customer debt</th><th>Supplier debt</th><th>Action</th></tr></thead>
                <tbody>
                  {branchRows.map((row) => (
                    <tr key={row.id}>
                      <td><strong>{row.name}</strong><small>{row.code}{row.isMain ? " · Main" : ""}<br />Revenue rank #{row.revenueRank}</small></td>
                      <td>{formatCurrency(numberValue(row.revenue))}</td>
                      <td>{formatCurrency(numberValue(row.grossProfit))}<small>{numberValue(row.profitMargin).toFixed(2)}%</small></td>
                      <td>{row.availableStockUnits}</td>
                      <td>{row.lowStockCount} / {row.stockoutCount}</td>
                      <td>{formatCurrency(numberValue(row.customerDebt))}</td>
                      <td>{formatCurrency(numberValue(row.supplierDebt))}</td>
                      <td><button type="button" onClick={() => switchBranch(row.id)}>Work here</button></td>
                    </tr>
                  ))}
                  {!branchRows.length ? <tr><td colSpan="8">No active branches found.</td></tr> : null}
                </tbody>
              </table>
            </div>
          </section>

          <div className="intelligence-branch-two-column">
            <section className="intelligence-panel">
              <div className="intelligence-panel-heading">
                <div><span>Branch setup</span><h3>Add a physical location</h3><small>New branches start with zero stock for every catalogue product.</small></div>
              </div>
              <form className="intelligence-branch-form" onSubmit={createBranch}>
                <label><span>Branch name</span><input required value={branchForm.name} onChange={(event) => setBranchForm({...branchForm, name:event.target.value})} placeholder="Kumasi Branch" /></label>
                <label><span>Code</span><input required value={branchForm.code} onChange={(event) => setBranchForm({...branchForm, code:event.target.value})} placeholder="KSI" /></label>
                <label><span>Location</span><input value={branchForm.location} onChange={(event) => setBranchForm({...branchForm, location:event.target.value})} placeholder="Adum, Kumasi" /></label>
                <label><span>Phone</span><input value={branchForm.phone} onChange={(event) => setBranchForm({...branchForm, phone:event.target.value})} placeholder="0240000000" /></label>
                <button className="intelligence-primary-action" disabled={actionLoading}><PackagePlus size={16} /> Create branch</button>
              </form>
            </section>

            <section className="intelligence-panel">
              <div className="intelligence-panel-heading">
                <div><span>Confirmed action</span><h3>Transfer stock between branches</h3><small>Company total stock remains unchanged.</small></div>
              </div>
              <form className="intelligence-branch-form" onSubmit={createTransfer}>
                <label><span>From</span><select required value={transferForm.sourceBranchId} onChange={(event) => setTransferForm({...transferForm, sourceBranchId:event.target.value, productId:""})}><option value="">Select source</option>{branches.filter((item)=>item.isActive).map((item)=><option value={item.id} key={item.id}>{item.name}</option>)}</select></label>
                <label><span>To</span><select required value={transferForm.destinationBranchId} onChange={(event) => setTransferForm({...transferForm, destinationBranchId:event.target.value})}><option value="">Select destination</option>{branches.filter((item)=>item.isActive && item.id!==transferForm.sourceBranchId).map((item)=><option value={item.id} key={item.id}>{item.name}</option>)}</select></label>
                <label className="wide"><span>Product</span><select required value={transferForm.productId} onChange={(event) => setTransferForm({...transferForm, productId:event.target.value})}><option value="">Select product</option>{sourceInventory.filter((item)=>Number(item.availableStock)>0).map((item)=><option value={item.productId} key={item.id}>{item.productName} · {item.availableStock} {item.unit}(s) available</option>)}</select></label>
                <label><span>Quantity</span><input type="number" min="1" required value={transferForm.quantity} onChange={(event) => setTransferForm({...transferForm, quantity:event.target.value})} /></label>
                <label><span>Reason</span><input value={transferForm.reason} onChange={(event) => setTransferForm({...transferForm, reason:event.target.value})} placeholder="Balance stock between branches" /></label>
                <button className="intelligence-primary-action" disabled={actionLoading}><ArrowRightLeft size={16} /> Review & transfer</button>
              </form>
            </section>
          </div>

          <section className="intelligence-panel">
            <div className="intelligence-panel-heading">
              <div><span>Deterministic recommendations</span><h3>Transfer before restocking</h3><small>Suggestions are read-only until you explicitly confirm a transfer.</small></div>
              <ShieldCheck size={20} />
            </div>
            <div className="intelligence-branch-suggestions">
              {suggestions.map((item) => (
                <article key={`${item.productId}-${item.sourceBranchId}-${item.destinationBranchId}`}>
                  <div><strong>{item.productName}</strong><span>{item.sourceBranchName} → {item.destinationBranchName}</span><small>{item.reason}</small></div>
                  <div><strong>{item.suggestedQuantity} {item.unit}(s)</strong><button type="button" onClick={() => prepareSuggestion(item)}>Prepare transfer</button></div>
                </article>
              ))}
              {!suggestions.length ? <p>No safe inter-branch transfer opportunities are currently required.</p> : null}
            </div>
          </section>

          <section className="intelligence-panel">
            <div className="intelligence-panel-heading">
              <div><span>Staff isolation</span><h3>Assign staff to branches</h3><small>Owners and managers can see all branches. Assign operational staff only where they should work.</small></div>
              <Users size={20} />
            </div>
            <div className="intelligence-branch-access-grid">
              {branches.filter((item)=>item.isActive).map((item) => (
                <button type="button" key={item.id} className={accessBranchId===item.id ? "active" : ""} onClick={() => openBranchAccess(item)}>
                  <strong>{item.name}</strong><span>{item.assignedMemberIds?.length || 0} assigned membership(s)</span>
                </button>
              ))}
            </div>
            {accessBranchId ? (
              <div className="intelligence-branch-members">
                {activeTeam.map((member) => (
                  <label key={member.id}>
                    <input type="checkbox" checked={membershipIds.includes(String(member.id))} onChange={() => toggleMembership(member.id)} />
                    <span><strong>{member.name}</strong><small>{member.role.replaceAll("_", " ")}</small></span>
                  </label>
                ))}
                <button type="button" className="intelligence-primary-action" onClick={saveBranchAccess} disabled={actionLoading}>Save branch access</button>
              </div>
            ) : null}
          </section>

          <section className="intelligence-panel">
            <div className="intelligence-panel-heading">
              <div><span>Audit trail</span><h3>Recent branch transfers</h3><small>Completed stock movements remain traceable.</small></div>
            </div>
            <div className="intelligence-branch-transfer-list">
              {transfers.slice(0, 10).map((item) => (
                <article key={item.id}>
                  <div><strong>{item.transferNumber}</strong><span>{item.sourceBranchName} → {item.destinationBranchName}</span></div>
                  <div><strong>{item.items.map((line)=>`${line.productName}: ${line.quantity}`).join(", ")}</strong><small>{dateTimeLabel(item.completedAt || item.createdAt)}</small></div>
                </article>
              ))}
              {!transfers.length ? <p>No branch transfers recorded yet.</p> : null}
            </div>
          </section>
        </>
      )}

      <Modal
        open={Boolean(pendingTransfer)}
        onClose={() => {
          if (actionLoading) return;
          setPendingTransfer(null);
          setTransferConfirmError("");
        }}
        title="Confirm stock transfer"
        description="Review this movement before StockFlow changes branch balances."
      >
        {pendingTransfer ? (
          <div className="intelligence-transfer-confirmation">
            <div className="intelligence-transfer-confirm-route">
              <div>
                <span>From</span>
                <strong>{pendingTransfer.sourceBranchName}</strong>
              </div>
              <ArrowRightLeft size={20} aria-hidden="true" />
              <div>
                <span>To</span>
                <strong>{pendingTransfer.destinationBranchName}</strong>
              </div>
            </div>

            <div className="intelligence-transfer-confirm-grid">
              <div>
                <span>Product</span>
                <strong>{pendingTransfer.productName}</strong>
              </div>
              <div>
                <span>Quantity</span>
                <strong>
                  {pendingTransfer.quantity} {pendingTransfer.unit}(s)
                </strong>
              </div>
              <div>
                <span>Reason</span>
                <strong>{pendingTransfer.reason || "No reason recorded"}</strong>
              </div>
            </div>

            <div className="intelligence-transfer-confirm-safety">
              <ShieldCheck size={19} aria-hidden="true" />
              <div>
                <strong>Company inventory remains unchanged</strong>
                <span>
                  StockFlow will move this quantity between locations only. The
                  business-wide product total will not increase or decrease.
                </span>
              </div>
            </div>

            {transferConfirmError ? (
              <div className="intelligence-transfer-confirm-error" role="alert">
                {transferConfirmError}
              </div>
            ) : null}

            <div className="intelligence-transfer-confirm-actions">
              <Button
                variant="secondary"
                onClick={() => {
                  setPendingTransfer(null);
                  setTransferConfirmError("");
                }}
                disabled={actionLoading}
              >
                Cancel
              </Button>
              <Button onClick={confirmTransfer} disabled={actionLoading}>
                {actionLoading ? (
                  <LoaderCircle
                    size={17}
                    className="intelligence-transfer-confirm-spinner"
                    aria-hidden="true"
                  />
                ) : (
                  <ArrowRightLeft size={17} aria-hidden="true" />
                )}
                {actionLoading ? "Transferring..." : "Confirm transfer"}
              </Button>
            </div>
          </div>
        ) : null}
      </Modal>
    </div>
  );
}
