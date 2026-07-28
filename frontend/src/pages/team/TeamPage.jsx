import { Mail, Plus, Search, ShieldCheck, UserRoundCog } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Modal from "../../components/ui/Modal";
import PageHeader from "../../components/ui/PageHeader";
import { useStore } from "../../context/StoreContext";
import { formatDateTime } from "../../utils/formatters";

import "../../styles/team-page-polish.css";

export default function TeamPage() {
  const {
    team,
    business,
    addTeamMember,
    deleteTeamMember,
  } = useStore();
  const [search, setSearch] = useState("");
  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState({ name: "", email: "", phone: "", role: "cashier" });
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [deleteMemberTarget, setDeleteMemberTarget] = useState(null);
  const [deleteError, setDeleteError] = useState("");

  const filtered = useMemo(
    () =>
      team.filter((member) =>
        [member.name, member.email, member.phone, member.role]
          .filter(Boolean)
          .some((value) =>
            String(value)
              .toLowerCase()
              .includes(search.trim().toLowerCase()),
          ),
      ),
    [search, team],
  );

  const totalPages = Math.max(
    1,
    Math.ceil(filtered.length / pageSize),
  );

  const safeCurrentPage = Math.min(currentPage, totalPages);

  const paginatedTeam = useMemo(() => {
    const startIndex = (safeCurrentPage - 1) * pageSize;

    return filtered.slice(startIndex, startIndex + pageSize);
  }, [filtered, pageSize, safeCurrentPage]);

  const firstVisibleRecord = filtered.length
    ? (safeCurrentPage - 1) * pageSize + 1
    : 0;

  const lastVisibleRecord = filtered.length
    ? firstVisibleRecord + paginatedTeam.length - 1
    : 0;

  // Returns to page one whenever search or page size changes.
  useEffect(() => {
    setCurrentPage(1);
  }, [search, pageSize]);

  // Keeps the selected page inside the available page range.
  useEffect(() => {
    if (currentPage > totalPages) {
      setCurrentPage(totalPages);
    }
  }, [currentPage, totalPages]);

  function submit(event) {
    event.preventDefault();
    addTeamMember(form);
    setForm({ name: "", email: "", phone: "", role: "cashier" });
    setModalOpen(false);
  }

  // Removes a staff member after confirmation while protecting the owner.
  function confirmTeamMemberDeletion() {
    if (!deleteMemberTarget) return;

    setDeleteError("");

    try {
      deleteTeamMember(deleteMemberTarget.id);
      setDeleteMemberTarget(null);
    } catch (error) {
      setDeleteError(error.message);
    }
  }

  return (
    <div className="page-stack">
      <PageHeader eyebrow="Access control" title="Team members" description="Give each worker an individual account and role instead of sharing the owner password." actions={<Button onClick={() => setModalOpen(true)}><Plus size={18} /> Add team member</Button>} />

      <section className="permission-callout"><ShieldCheck size={23} /><div><strong>Role-based protection is part of the architecture.</strong><p>Cashiers should not automatically view full profit, change cost prices, reverse sales or manage subscriptions.</p></div></section>

      <section className="panel-card">
        <div className="table-toolbar"><label className="table-search"><Search size={18} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search name, email or role..." /></label><span className="result-count">{filtered.length} team member(s)</span></div>
        <div className="team-card-grid">
          {paginatedTeam.map((member) => (
            <article className="team-card" key={member.id}>
              <div className="team-card-heading"><span>{member.name.slice(0, 2).toUpperCase()}</span><div><strong>{member.name}</strong><small className="capitalize-text">{member.role}</small></div><Badge tone={member.status === "active" ? "success" : "neutral"}>{member.status}</Badge></div>
              <div className="team-contact"><span><Mail size={16} />{member.email}</span><span>{member.phone}</span></div>
              <div className="team-card-footer">
                <div>
                  <span>Last active</span>
                  <strong>
                    {member.lastActive
                      ? formatDateTime(member.lastActive)
                      : "Not yet"}
                  </strong>
                </div>

                {member.role !== "owner" ? (
                  <button
                    type="button"
                    className="team-member-delete-action"
                    onClick={() => {
                      setDeleteError("");
                      setDeleteMemberTarget(member);
                    }}
                  >
                    Remove
                  </button>
                ) : (
                  <span className="team-owner-protected-label">
                    Protected owner
                  </span>
                )}
              </div>
            </article>
          ))}
        </div>

        <div className="team-pagination">
          <div className="team-pagination-summary">
            <span>
              Showing {firstVisibleRecord}-{lastVisibleRecord} of{" "}
              {filtered.length} team members
            </span>

            <label>
              Rows per page
              <select
                value={pageSize}
                onChange={(event) =>
                  setPageSize(Number(event.target.value))
                }
              >
                <option value="10">10</option>
                <option value="20">20</option>
                <option value="50">50</option>
              </select>
            </label>
          </div>

          <div className="team-pagination-controls">
            <button
              type="button"
              onClick={() =>
                setCurrentPage((page) => Math.max(1, page - 1))
              }
              disabled={safeCurrentPage === 1}
            >
              Previous
            </button>

            <span>
              Page {safeCurrentPage} of {totalPages}
            </span>

            <button
              type="button"
              onClick={() =>
                setCurrentPage((page) =>
                  Math.min(totalPages, page + 1),
                )
              }
              disabled={safeCurrentPage === totalPages}
            >
              Next
            </button>
          </div>
        </div>
      </section>

      <Modal
        open={Boolean(deleteMemberTarget)}
        onClose={() => {
          setDeleteMemberTarget(null);
          setDeleteError("");
        }}
        title="Remove team member"
        description={
          deleteMemberTarget
            ? `Remove ${deleteMemberTarget.name} from ${business?.name || "this business"}?`
            : ""
        }
      >
        {deleteError ? (
          <div className="form-alert form-alert-error">
            {deleteError}
          </div>
        ) : null}

        <div className="team-delete-confirmation">
          <p>
            This removes the staff account only from the currently active
            business. The owner account cannot be deleted.
          </p>

          <div className="modal-form-actions">
            <Button
              variant="secondary"
              onClick={() => {
                setDeleteMemberTarget(null);
                setDeleteError("");
              }}
            >
              Cancel
            </Button>

            <Button
              className="team-delete-confirm-button"
              onClick={confirmTeamMemberDeletion}
            >
              Remove team member
            </Button>
          </div>
        </div>
      </Modal>

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title="Add team member" description="The backend phase will send a secure invitation and temporary password.">
        <form className="simple-form" onSubmit={submit}>
          <label>Full name<input value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} required /></label>
          <label>Email address<input type="email" value={form.email} onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))} required /></label>
          <label>Phone number<input value={form.phone} onChange={(event) => setForm((current) => ({ ...current, phone: event.target.value }))} /></label>
          <label>Role<select value={form.role} onChange={(event) => setForm((current) => ({ ...current, role: event.target.value }))}><option value="cashier">Cashier</option><option value="manager">Manager</option><option value="inventory_clerk">Inventory clerk</option></select></label>
          <div className="role-preview"><UserRoundCog size={21} /><div><strong className="capitalize-text">{form.role.replace("_", " ")}</strong><span>Permissions will be enforced by both the frontend and Django API.</span></div></div>
          <div className="modal-form-actions"><Button variant="secondary" onClick={() => setModalOpen(false)}>Cancel</Button><Button type="submit">Add team member</Button></div>
        </form>
      </Modal>
    </div>
  );
}
