import {
  Copy,
  Mail,
  Plus,
  Search,
  ShieldCheck,
  UserRoundCog,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Modal from "../../components/ui/Modal";
import PageHeader from "../../components/ui/PageHeader";
import { useStore } from "../../context/StoreContext";
import { formatDateTime } from "../../utils/formatters";

import "../../styles/team-page-polish.css";

const EMPTY_FORM = {
  name: "",
  email: "",
  phone: "",
  role: "cashier",
};

export default function TeamPage() {
  const {
    team,
    teamLoading,
    teamError,
    business,
    addTeamMember,
    deleteTeamMember,
  } = useStore();

  const [search, setSearch] = useState("");
  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [deleteMemberTarget, setDeleteMemberTarget] = useState(null);
  const [deleteError, setDeleteError] = useState("");
  const [actionError, setActionError] = useState("");
  const [actionMessage, setActionMessage] = useState("");
  const [temporaryPassword, setTemporaryPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [deleting, setDeleting] = useState(false);

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

  useEffect(() => {
    setCurrentPage(1);
  }, [search, pageSize]);

  useEffect(() => {
    if (currentPage > totalPages) {
      setCurrentPage(totalPages);
    }
  }, [currentPage, totalPages]);

  async function submit(event) {
    event.preventDefault();

    if (submitting) return;

    setSubmitting(true);
    setActionError("");
    setActionMessage("");
    setTemporaryPassword("");

    try {
      const nextMember = await addTeamMember(form);

      setForm(EMPTY_FORM);
      setModalOpen(false);
      setTemporaryPassword(nextMember.temporaryPassword || "");
      setActionMessage(
        nextMember.isNewUser
          ? `${nextMember.name} was added with a new staff account.`
          : `${nextMember.name} was added to ${business.name}.`,
      );
    } catch (error) {
      setActionError(error.message);
    } finally {
      setSubmitting(false);
    }
  }

  async function confirmTeamMemberDeletion() {
    if (!deleteMemberTarget || deleting) return;

    setDeleting(true);
    setDeleteError("");

    try {
      await deleteTeamMember(deleteMemberTarget.id);
      setActionMessage(
        `${deleteMemberTarget.name} was removed from ${business.name}.`,
      );
      setDeleteMemberTarget(null);
    } catch (error) {
      setDeleteError(error.message);
    } finally {
      setDeleting(false);
    }
  }

  async function copyTemporaryPassword() {
    try {
      await navigator.clipboard.writeText(temporaryPassword);
      setActionMessage("Temporary password copied.");
    } catch {
      setActionError(
        "Copy failed. Select and copy the temporary password manually.",
      );
    }
  }

  return (
    <div className="page-stack team-page">
      <PageHeader
        eyebrow="Access control"
        title="Team members"
        description="Give each worker an individual account and role instead of sharing the owner password."
        actions={
          <Button
            onClick={() => {
              setActionError("");
              setModalOpen(true);
            }}
          >
            <Plus size={18} />
            Add team member
          </Button>
        }
      />

      {teamLoading ? (
        <div className="form-alert" role="status">
          Loading team members...
        </div>
      ) : null}

      {teamError || actionError ? (
        <div className="form-alert form-alert-error" role="alert">
          {actionError || teamError}
        </div>
      ) : null}

      {actionMessage ? (
        <div className="form-alert form-alert-success" role="status">
          {actionMessage}
        </div>
      ) : null}

      {temporaryPassword ? (
        <section className="permission-callout">
          <ShieldCheck size={23} />
          <div>
            <strong>Copy this temporary password now.</strong>
            <p>
              It is shown only after creating a new staff account. Send it
              privately to the staff member and ask them to change it after
              login.
            </p>
            <code>{temporaryPassword}</code>
          </div>
          <Button variant="secondary" onClick={copyTemporaryPassword}>
            <Copy size={17} />
            Copy password
          </Button>
        </section>
      ) : null}

      <section className="permission-callout">
        <ShieldCheck size={23} />
        <div>
          <strong>Role-based protection is active.</strong>
          <p>
            Cashiers cannot automatically view restricted cost information or
            manage business access.
          </p>
        </div>
      </section>

      <section className="panel-card">
        <div className="table-toolbar">
          <label className="table-search">
            <Search size={18} />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search name, email or role..."
            />
          </label>
          <span className="result-count">
            {filtered.length} team member(s)
          </span>
        </div>

        <div className="team-card-grid">
          {paginatedTeam.map((member) => (
            <article className="team-card" key={member.id}>
              <div className="team-card-heading">
                <span>
                  {(member.name || member.email)
                    .slice(0, 2)
                    .toUpperCase()}
                </span>
                <div>
                  <strong>{member.name || member.email}</strong>
                  <small className="capitalize-text">
                    {member.role.replace("_", " ")}
                  </small>
                </div>
                <Badge
                  tone={
                    member.status === "active" ? "success" : "neutral"
                  }
                >
                  {member.status}
                </Badge>
              </div>

              <div className="team-contact">
                <span>
                  <Mail size={16} />
                  {member.email}
                </span>
                <span>{member.phone || "No phone added"}</span>
              </div>

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

          {!teamLoading && !teamError && !filtered.length ? (
            <p className="muted-message">
              No team members match the current search.
            </p>
          ) : null}
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
          if (deleting) return;
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
            This removes access only from the active business. Historical
            records remain protected.
          </p>

          <div className="modal-form-actions">
            <Button
              variant="secondary"
              onClick={() => {
                setDeleteMemberTarget(null);
                setDeleteError("");
              }}
              disabled={deleting}
            >
              Cancel
            </Button>

            <Button
              className="team-delete-confirm-button"
              onClick={confirmTeamMemberDeletion}
              disabled={deleting}
            >
              {deleting ? "Removing..." : "Remove team member"}
            </Button>
          </div>
        </div>
      </Modal>

      <Modal
        open={modalOpen}
        onClose={() => {
          if (!submitting) setModalOpen(false);
        }}
        title="Add team member"
        description="A new staff account receives a temporary password once. Existing users are added with their existing login."
      >
        <form className="simple-form" onSubmit={submit}>
          <label>
            Full name
            <input
              value={form.name}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  name: event.target.value,
                }))
              }
              required
            />
          </label>

          <label>
            Email address
            <input
              type="email"
              value={form.email}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  email: event.target.value,
                }))
              }
              required
            />
          </label>

          <label>
            Phone number
            <input
              value={form.phone}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  phone: event.target.value,
                }))
              }
            />
          </label>

          <label>
            Role
            <select
              value={form.role}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  role: event.target.value,
                }))
              }
            >
              <option value="cashier">Cashier</option>
              <option value="manager">Manager</option>
              <option value="inventory_clerk">
                Inventory clerk
              </option>
            </select>
          </label>

          <div className="role-preview">
            <UserRoundCog size={21} />
            <div>
              <strong className="capitalize-text">
                {form.role.replace("_", " ")}
              </strong>
              <span>
                Permissions are enforced by both React and Django.
              </span>
            </div>
          </div>

          <div className="modal-form-actions">
            <Button
              variant="secondary"
              onClick={() => setModalOpen(false)}
              disabled={submitting}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? "Adding..." : "Add team member"}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
