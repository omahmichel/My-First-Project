import {
  Activity,
  AlertTriangle,
  CalendarClock,
  CheckCircle2,
  Clock3,
  LoaderCircle,
  Play,
  Plus,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Trash2,
  XCircle,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useStore } from "../../context/StoreContext";
import { apiRequest } from "../../services/api";
import {
  formatDateTime,
  titleCase,
} from "./intelligenceUtils";


const RULES = [
  {
    value: "risk_monitor",
    label: "Business risk monitor",
    description:
      "Hourly checks for stock, forecasts, sales, margin, debt, large discounts and unusual manual stock adjustments.",
  },
  {
    value: "daily_closing",
    label: "Daily closing summary",
    description:
      "Generates a verified Daily Business Summary at your chosen Ghana-time hour.",
  },
  {
    value: "weekly_management",
    label: "Weekly management summary",
    description:
      "Generates a verified Weekly Management Report on the selected weekday and Ghana-time hour.",
  },
];

const WEEKDAYS = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];


function scheduleLabel(rule) {
  if (rule.scheduleFrequency === "hourly") return "Every hour";

  const hour = String(rule.hourUtc ?? 0).padStart(2, "0");

  if (rule.scheduleFrequency === "daily") {
    return `Daily at ${hour}:00 Ghana time`;
  }

  return `${WEEKDAYS[rule.weekday ?? 0] || "Monday"} at ${hour}:00 Ghana time`;
}


function StatusIcon({ status }) {
  if (status === "completed") return <CheckCircle2 size={15} />;
  if (status === "failed") return <XCircle size={15} />;
  return <Clock3 size={15} />;
}


export default function IntelligenceAutomationPage() {
  const { business } = useStore();
  const [rules, setRules] = useState([]);
  const [events, setEvents] = useState([]);
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [workingId, setWorkingId] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [deleteRuleTarget, setDeleteRuleTarget] = useState(null);
  const [form, setForm] = useState({
    ruleType: "risk_monitor",
    isEnabled: true,
    hourUtc: 18,
    weekday: 0,
    includeAiSummary: false,
    largeDiscountPercent: 20,
    stockAdjustmentPercent: 25,
    stockAdjustmentMinUnits: 5,
  });

  const loadAutomation = useCallback(async () => {
    if (!business.id) return;

    setLoading(true);
    setError("");

    try {
      const [ruleData, eventData, runData] = await Promise.all([
        apiRequest(
          `/businesses/${business.id}/intelligence/automation/rules/`,
        ),
        apiRequest(
          `/businesses/${business.id}/intelligence/automation/events/?limit=50`,
        ),
        apiRequest(
          `/businesses/${business.id}/intelligence/automation/runs/`,
        ),
      ]);

      setRules(Array.isArray(ruleData) ? ruleData : []);
      setEvents(Array.isArray(eventData) ? eventData : []);
      setRuns(Array.isArray(runData) ? runData : []);
    } catch (requestError) {
      setError(
        requestError.message ||
          "Automation data could not be loaded.",
      );
    } finally {
      setLoading(false);
    }
  }, [business.id]);

  useEffect(() => {
    setRules([]);
    setEvents([]);
    setRuns([]);
    setNotice("");
    loadAutomation();
  }, [loadAutomation]);

  const visibleRules = useMemo(
    () => rules.filter((rule) => rule.businessId === business.id),
    [rules, business.id],
  );
  const visibleEvents = useMemo(
    () => events.filter((event) => event.businessId === business.id),
    [events, business.id],
  );
  const visibleRuns = useMemo(
    () => runs.filter((run) => run.businessId === business.id),
    [runs, business.id],
  );

  async function createRule() {
    if (!business.id || creating) return;

    setCreating(true);
    setError("");
    setNotice("");

    const payload = {
      ruleType: form.ruleType,
      isEnabled: form.isEnabled,
    };

    if (form.ruleType === "risk_monitor") {
      payload.largeDiscountPercent = Number(form.largeDiscountPercent);
      payload.stockAdjustmentPercent = Number(form.stockAdjustmentPercent);
      payload.stockAdjustmentMinUnits = Number(form.stockAdjustmentMinUnits);
    } else {
      payload.hourUtc = Number(form.hourUtc);
      payload.includeAiSummary = form.includeAiSummary;

      if (form.ruleType === "weekly_management") {
        payload.weekday = Number(form.weekday);
      }
    }

    try {
      await apiRequest(
        `/businesses/${business.id}/intelligence/automation/rules/`,
        {
          method: "POST",
          body: JSON.stringify(payload),
        },
      );
      setNotice("Automation rule created successfully.");
      await loadAutomation();
    } catch (requestError) {
      setError(
        requestError.message ||
          "The automation rule could not be created.",
      );
    } finally {
      setCreating(false);
    }
  }

  async function patchRule(rule, changes) {
    setWorkingId(rule.id);
    setError("");
    setNotice("");

    try {
      await apiRequest(
        `/businesses/${business.id}/intelligence/automation/rules/${rule.id}/`,
        {
          method: "PATCH",
          body: JSON.stringify(changes),
        },
      );
      setNotice("Automation rule updated.");
      await loadAutomation();
    } catch (requestError) {
      setError(
        requestError.message ||
          "The automation rule could not be updated.",
      );
    } finally {
      setWorkingId("");
    }
  }

  async function runNow(rule) {
    setWorkingId(rule.id);
    setError("");
    setNotice("");

    try {
      const run = await apiRequest(
        `/businesses/${business.id}/intelligence/automation/rules/${rule.id}/run/`,
        {
          method: "POST",
          body: JSON.stringify({}),
        },
      );

      setNotice(
        run.status === "completed"
          ? `Automation completed. ${run.eventCount} new event(s) created.`
          : run.errorMessage || "Automation execution failed safely.",
      );
      await loadAutomation();
    } catch (requestError) {
      setError(
        requestError.message ||
          "The automation could not be run.",
      );
    } finally {
      setWorkingId("");
    }
  }

  async function deleteRule(rule) {
    if (!rule || workingId) return;

    setWorkingId(rule.id);
    setError("");
    setNotice("");

    try {
      await apiRequest(
        `/businesses/${business.id}/intelligence/automation/rules/${rule.id}/`,
        { method: "DELETE" },
      );
      setDeleteRuleTarget(null);
      setNotice(
        "Automation rule removed. Existing event and run history was preserved.",
      );
      await loadAutomation();
    } catch (requestError) {
      setError(
        requestError.message ||
          "The automation rule could not be removed.",
      );
    } finally {
      setWorkingId("");
    }
  }

  const selectedRule =
    RULES.find((item) => item.value === form.ruleType) || RULES[0];

  return (
    <div className="intelligence-page intelligence-automation-page">
      <section className="intelligence-page-hero">
        <div>
          <span className="intelligence-eyebrow">
            <Sparkles size={15} />
            Automation engine
          </span>
          <h2>Let StockFlow monitor important business signals for you.</h2>
          <p>
            Rules create advisory Intelligence events and verified reports.
            They never change stock, prices, sales, debts or payments
            automatically.
          </p>
        </div>

        <div className="intelligence-ask-readonly">
          <ShieldCheck size={18} />
          <div>
            <strong>Confirmation remains in your control</strong>
            <span>
              Scheduled Intelligence is read-only toward transactional records.
            </span>
          </div>
        </div>
      </section>

      <section className="intelligence-automation-runner">
        <Activity size={18} />
        <div>
          <strong>Lightweight Django automation worker</strong>
          <span>
            Due rules are processed by StockFlow's management command. No
            Redis, Celery or third-party scheduler is required.
          </span>
        </div>
        <button type="button" onClick={loadAutomation} disabled={loading}>
          <RefreshCw size={15} />
          Refresh
        </button>
      </section>

      {error ? (
        <div className="intelligence-ask-error" role="alert">
          <AlertTriangle size={19} />
          <div>
            <strong>Automation action failed</strong>
            <span>{error}</span>
          </div>
        </div>
      ) : null}

      {notice ? (
        <div className="intelligence-report-notice" role="status">
          {notice}
        </div>
      ) : null}

      <section className="intelligence-automation-builder">
        <div>
          <span>Create automation</span>
          <h3>{selectedRule.label}</h3>
          <p>{selectedRule.description}</p>
        </div>

        <div className="intelligence-automation-form">
          <label>
            <span>Rule type</span>
            <select
              value={form.ruleType}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  ruleType: event.target.value,
                  hourUtc:
                    event.target.value === "weekly_management" ? 8 : 18,
                }))
              }
            >
              {RULES.map((rule) => (
                <option value={rule.value} key={rule.value}>
                  {rule.label}
                </option>
              ))}
            </select>
          </label>

          {form.ruleType !== "risk_monitor" ? (
            <>
              <label>
                <span>Ghana-time hour</span>
                <select
                  value={form.hourUtc}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      hourUtc: event.target.value,
                    }))
                  }
                >
                  {Array.from({ length: 24 }, (_, hour) => (
                    <option value={hour} key={hour}>
                      {String(hour).padStart(2, "0")}:00
                    </option>
                  ))}
                </select>
              </label>

              {form.ruleType === "weekly_management" ? (
                <label>
                  <span>Weekday</span>
                  <select
                    value={form.weekday}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        weekday: event.target.value,
                      }))
                    }
                  >
                    {WEEKDAYS.map((day, index) => (
                      <option value={index} key={day}>
                        {day}
                      </option>
                    ))}
                  </select>
                </label>
              ) : null}

              <label className="intelligence-automation-check">
                <input
                  type="checkbox"
                  checked={form.includeAiSummary}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      includeAiSummary: event.target.checked,
                    }))
                  }
                />
                <span>
                  <strong>Include AI narrative</strong>
                  <small>
                    Optional and uses API credits. Django figures stay
                    authoritative.
                  </small>
                </span>
              </label>
            </>
          ) : (
            <div className="intelligence-automation-thresholds">
              <label>
                <span>Large discount</span>
                <input
                  type="number"
                  min="1"
                  max="100"
                  value={form.largeDiscountPercent}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      largeDiscountPercent: event.target.value,
                    }))
                  }
                />
                <small>% of sale subtotal</small>
              </label>
              <label>
                <span>Stock adjustment</span>
                <input
                  type="number"
                  min="1"
                  value={form.stockAdjustmentPercent}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      stockAdjustmentPercent: event.target.value,
                    }))
                  }
                />
                <small>% of previous stock</small>
              </label>
              <label>
                <span>Minimum units</span>
                <input
                  type="number"
                  min="1"
                  value={form.stockAdjustmentMinUnits}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      stockAdjustmentMinUnits: event.target.value,
                    }))
                  }
                />
                <small>avoids tiny corrections</small>
              </label>
            </div>
          )}

          <label className="intelligence-automation-check">
            <input
              type="checkbox"
              checked={form.isEnabled}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  isEnabled: event.target.checked,
                }))
              }
            />
            <span>
              <strong>Enable after creation</strong>
              <small>You can disable or run it manually at any time.</small>
            </span>
          </label>

          <button type="button" onClick={createRule} disabled={creating}>
            {creating ? (
              <LoaderCircle className="intelligence-spin" size={16} />
            ) : (
              <Plus size={16} />
            )}
            {creating ? "Creating..." : "Create rule"}
          </button>
        </div>
      </section>

      <section className="intelligence-automation-grid">
        <article className="intelligence-automation-panel">
          <header>
            <CalendarClock size={17} />
            <div>
              <span>Automation rules</span>
              <strong>{visibleRules.length} configured</strong>
            </div>
          </header>

          {loading ? (
            <p className="intelligence-report-empty">
              Loading automation rules...
            </p>
          ) : visibleRules.length ? (
            <div className="intelligence-automation-rule-list">
              {visibleRules.map((rule) => (
                <div className="intelligence-automation-rule" key={rule.id}>
                  <div className="intelligence-automation-rule-main">
                    <div>
                      <strong>
                        {RULES.find((item) => item.value === rule.ruleType)
                          ?.label || titleCase(rule.ruleType)}
                      </strong>
                      <span>{scheduleLabel(rule)}</span>
                    </div>
                    <span
                      className={
                        rule.isEnabled
                          ? "intelligence-automation-state intelligence-automation-state-on"
                          : "intelligence-automation-state"
                      }
                    >
                      {rule.isEnabled ? "Enabled" : "Disabled"}
                    </span>
                  </div>

                  <div className="intelligence-automation-rule-meta">
                    <span>
                      Next: {rule.nextRunAt
                        ? formatDateTime(rule.nextRunAt)
                        : "Not scheduled"}
                    </span>
                    <span>
                      Last: {rule.lastRunAt
                        ? formatDateTime(rule.lastRunAt)
                        : "Never"}
                    </span>
                    {rule.lastStatus ? (
                      <span className={`automation-${rule.lastStatus}`}>
                        <StatusIcon status={rule.lastStatus} />
                        {titleCase(rule.lastStatus)}
                        {rule.consecutiveFailures
                          ? ` · ${rule.consecutiveFailures} failure(s)`
                          : ""}
                      </span>
                    ) : null}
                  </div>

                  <div className="intelligence-automation-rule-actions">
                    <button
                      type="button"
                      onClick={() =>
                        patchRule(rule, { isEnabled: !rule.isEnabled })
                      }
                      disabled={workingId === rule.id}
                    >
                      {rule.isEnabled ? "Disable" : "Enable"}
                    </button>
                    <button
                      type="button"
                      onClick={() => runNow(rule)}
                      disabled={workingId === rule.id}
                    >
                      <Play size={14} />
                      {rule.lastStatus === "failed" ? "Retry" : "Run now"}
                    </button>
                    <button
                      type="button"
                      className="intelligence-automation-delete"
                      onClick={() => setDeleteRuleTarget(rule)}
                      disabled={workingId === rule.id}
                      aria-label="Remove automation rule"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="intelligence-report-empty">
              No automation rules yet. Create the first rule above.
            </p>
          )}
        </article>

        <article className="intelligence-automation-panel">
          <header>
            <AlertTriangle size={17} />
            <div>
              <span>Automation events</span>
              <strong>{visibleEvents.length} recent</strong>
            </div>
          </header>

          {visibleEvents.length ? (
            <div className="intelligence-automation-event-list">
              {visibleEvents.map((event) => (
                <div
                  key={event.id}
                  className={`intelligence-automation-event intelligence-automation-event-${event.severity}`}
                >
                  <div>
                    <strong>{event.title}</strong>
                    <span>{titleCase(event.eventType)}</span>
                  </div>
                  <p>{event.summary}</p>
                  <small>{formatDateTime(event.generatedAt)}</small>
                </div>
              ))}
            </div>
          ) : (
            <p className="intelligence-report-empty">
              No automation event has been generated yet.
            </p>
          )}
        </article>
      </section>

      <section className="intelligence-automation-panel intelligence-automation-runs">
        <header>
          <Clock3 size={17} />
          <div>
            <span>Execution history</span>
            <strong>{visibleRuns.length} recent run(s)</strong>
          </div>
        </header>

        {visibleRuns.length ? (
          <div className="intelligence-automation-run-list">
            {visibleRuns.map((run) => (
              <div key={run.id} className="intelligence-automation-run">
                <StatusIcon status={run.status} />
                <div>
                  <strong>
                    {titleCase(run.triggerType)} · {titleCase(run.status)}
                  </strong>
                  <span>
                    {run.eventCount} new event(s) · {formatDateTime(run.startedAt)}
                  </span>
                  {run.errorMessage ? <small>{run.errorMessage}</small> : null}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="intelligence-report-empty">
            No automation has been executed yet.
          </p>
        )}
      </section>

      <section className="intelligence-automation-safety">
        <ShieldCheck size={17} />
        <div>
          <strong>Automation may</strong>
          <p>
            Refresh Intelligence recommendations, create advisory events and
            generate Daily or Weekly management reports. AI can optionally
            explain a generated report.
          </p>
        </div>
        <div>
          <strong>Automation may not</strong>
          <p>
            Silently alter inventory, prices, sales, customer debt, supplier
            balances, payments or other transactional business records.
          </p>
        </div>
      </section>

      {deleteRuleTarget ? (
        <div className="intelligence-automation-confirm-backdrop">
          <section
            className="intelligence-automation-confirm-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="automation-delete-title"
          >
            <header>
              <div>
                <span>CONFIRM ACTION</span>
                <h3 id="automation-delete-title">Remove automation rule?</h3>
              </div>
              <button
                type="button"
                className="intelligence-automation-confirm-close"
                onClick={() => setDeleteRuleTarget(null)}
                disabled={workingId === deleteRuleTarget.id}
                aria-label="Close confirmation"
              >
                &times;
              </button>
            </header>

            <div className="intelligence-automation-confirm-body">
              <div className="intelligence-automation-confirm-warning">
                <AlertTriangle size={21} />
                <div>
                  <strong>
                    {RULES.find(
                      (item) => item.value === deleteRuleTarget.ruleType,
                    )?.label || titleCase(deleteRuleTarget.ruleType)}
                  </strong>
                  <p>
                    StockFlow will remove this automation rule. Existing event
                    and execution history will be preserved for audit purposes.
                  </p>
                </div>
              </div>

              <div className="intelligence-automation-confirm-note">
                <ShieldCheck size={18} />
                <span>
                  Removing this rule does not change inventory, sales, prices,
                  payments, customer debt or supplier balances.
                </span>
              </div>
            </div>

            <footer>
              <button
                type="button"
                className="intelligence-automation-confirm-cancel"
                onClick={() => setDeleteRuleTarget(null)}
                disabled={workingId === deleteRuleTarget.id}
              >
                Cancel
              </button>
              <button
                type="button"
                className="intelligence-automation-confirm-delete"
                onClick={() => deleteRule(deleteRuleTarget)}
                disabled={workingId === deleteRuleTarget.id}
              >
                <Trash2 size={15} />
                {workingId === deleteRuleTarget.id ? "Removing..." : "Remove rule"}
              </button>
            </footer>
          </section>
        </div>
      ) : null}
    </div>
  );
}
