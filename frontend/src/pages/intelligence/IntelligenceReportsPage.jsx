import {
  BrainCircuit,
  Download,
  FileBarChart2,
  History,
  LoaderCircle,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { useStore } from "../../context/StoreContext";
import { apiRequest } from "../../services/api";
import { exportIntelligenceReportPdf } from "../../utils/intelligenceReportExport";
import {
  formatDateTime,
  titleCase,
} from "./intelligenceUtils";


const REPORT_TYPES = [
  {
    value: "daily_summary",
    label: "Daily summary",
    description: "Today compared with the previous day at the same elapsed time.",
  },
  {
    value: "weekly_management",
    label: "Weekly management",
    description: "Seven-day sales, profit, trend and management attention.",
  },
  {
    value: "monthly_management",
    label: "Monthly management",
    description: "Thirty-day performance with comparable-period movement.",
  },
  {
    value: "sales_profit",
    label: "Sales & profit",
    description: "Verified revenue, historical cost, gross profit and margin.",
  },
  {
    value: "stock_risk_restocking",
    label: "Stock risk & restocking",
    description: "Stock-out, low-stock, slow-moving and dead-stock evidence.",
  },
  {
    value: "supplier_balances",
    label: "Supplier balances",
    description: "Current unpaid and partially paid restock purchases.",
  },
  {
    value: "customer_debt",
    label: "Customer debt",
    description: "Current customer receivables and outstanding invoice principal.",
  },
];


function formatMoney(value) {
  return `₵${Number(value || 0).toLocaleString("en-GH", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}


function formatValue(value, format) {
  if (format === "currency") return formatMoney(value);
  if (format === "percent") return `${Number(value || 0).toFixed(2)}%`;
  if (format === "boolean") return value ? "Yes" : "No";
  if (format === "date") {
    if (!value) return "Not recorded";
    return new Intl.DateTimeFormat("en-GH", {
      dateStyle: "medium",
    }).format(new Date(value));
  }
  if (format === "number") {
    return Number(value || 0).toLocaleString("en-GH");
  }
  return String(value ?? "Not recorded");
}


function QuestionBlock({ title, items }) {
  return (
    <article className="intelligence-report-question">
      <span>{title}</span>
      <div>
        {(items || []).map((item, index) => (
          <p key={`${title}-${index}`}>{item}</p>
        ))}
      </div>
    </article>
  );
}


export default function IntelligenceReportsPage() {
  const { business } = useStore();
  const [reports, setReports] = useState([]);
  const [selected, setSelected] = useState(null);
  const [reportType, setReportType] = useState("weekly_management");
  const [includeAi, setIncludeAi] = useState(false);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const selectedDefinition = useMemo(
    () =>
      REPORT_TYPES.find((item) => item.value === reportType) ||
      REPORT_TYPES[0],
    [reportType],
  );

  const visibleReports = useMemo(
    () =>
      reports.filter(
        (report) => report.businessId === business.id,
      ),
    [reports, business.id],
  );

  const selectedReport =
    selected?.businessId === business.id ? selected : null;

  useEffect(() => {
    let cancelled = false;

    async function loadReports() {
      if (!business.id) return;

      setLoading(true);
      setError("");

      try {
        const data = await apiRequest(
          `/businesses/${business.id}/intelligence/reports/`,
        );

        if (cancelled) return;

        const list = Array.isArray(data) ? data : [];
        setReports(list);
        setSelected(list[0] || null);
      } catch (requestError) {
        if (!cancelled) {
          setError(
            requestError.message ||
              "Intelligence reports could not be loaded.",
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadReports();

    return () => {
      cancelled = true;
    };
  }, [business.id]);

  async function handleGenerate() {
    if (!business.id || generating) return;

    setGenerating(true);
    setError("");
    setNotice("");

    try {
      const generated = await apiRequest(
        `/businesses/${business.id}/intelligence/reports/`,
        {
          method: "POST",
          body: JSON.stringify({
            reportType,
            includeAiSummary: includeAi,
          }),
        },
      );

      setReports((current) => [
        generated,
        ...current.filter((item) => item.id !== generated.id),
      ]);
      setSelected(generated);

      setNotice(
        generated.aiStatus === "unavailable" && includeAi
          ? "The verified report was created. The optional AI narrative was unavailable."
          : "Verified Intelligence report created successfully.",
      );
    } catch (requestError) {
      setError(
        requestError.message ||
          "The Intelligence report could not be generated.",
      );
    } finally {
      setGenerating(false);
    }
  }

  function handleDownload() {
    if (!selectedReport) return;

    try {
      const filename = exportIntelligenceReportPdf({
        business,
        report: selectedReport,
      });
      setNotice(`${filename} downloaded successfully.`);
      setError("");
    } catch (downloadError) {
      setError(
        downloadError.message ||
          "The Intelligence report PDF could not be created.",
      );
    }
  }

  const payload = selectedReport?.payload || {};
  const questions = payload.managementQuestions || {};
  const sections = payload.sections || [];

  return (
    <div className="intelligence-page intelligence-reports-page">
      <section className="intelligence-page-hero">
        <div>
          <span className="intelligence-eyebrow">
            <FileBarChart2 size={15} />
            Automated management reports
          </span>
          <h2>Turn verified StockFlow records into management reports.</h2>
          <p>
            Every figure is calculated by Django. AI is optional and can
            only explain the verified report; it never changes the figures.
          </p>
        </div>

        <div className="intelligence-ask-readonly">
          <ShieldCheck size={18} />
          <div>
            <strong>Authoritative figures</strong>
            <span>PDF downloads use GHS for reliable document rendering.</span>
          </div>
        </div>
      </section>

      {error ? (
        <div className="intelligence-ask-error" role="alert">
          <BrainCircuit size={20} />
          <div>
            <strong>Report action failed</strong>
            <span>{error}</span>
          </div>
        </div>
      ) : null}

      {notice ? (
        <div className="intelligence-report-notice" role="status">
          {notice}
        </div>
      ) : null}

      <section className="intelligence-report-builder">
        <div className="intelligence-report-builder-copy">
          <span>Generate report</span>
          <h3>{selectedDefinition.label}</h3>
          <p>{selectedDefinition.description}</p>
        </div>

        <div className="intelligence-report-builder-controls">
          <label>
            <span>Report type</span>
            <select
              value={reportType}
              onChange={(event) => setReportType(event.target.value)}
              disabled={generating}
            >
              {REPORT_TYPES.map((item) => (
                <option value={item.value} key={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>

          <label className="intelligence-report-ai-option">
            <input
              type="checkbox"
              checked={includeAi}
              onChange={(event) => setIncludeAi(event.target.checked)}
              disabled={generating}
            />
            <span>
              <strong>Include AI management narrative</strong>
              <small>Optional. Uses API credits; figures remain unchanged.</small>
            </span>
          </label>

          <button
            type="button"
            onClick={handleGenerate}
            disabled={generating}
          >
            {generating ? (
              <LoaderCircle className="intelligence-spin" size={17} />
            ) : (
              <Sparkles size={17} />
            )}
            {generating ? "Generating..." : "Generate report"}
          </button>
        </div>
      </section>

      <div className="intelligence-report-layout">
        <aside className="intelligence-report-history">
          <header>
            <History size={17} />
            <div>
              <span>Report history</span>
              <strong>{visibleReports.length} saved</strong>
            </div>
          </header>

          {loading ? (
            <p className="intelligence-report-empty">
              Loading saved reports...
            </p>
          ) : visibleReports.length ? (
            <div className="intelligence-report-history-list">
              {visibleReports.map((report) => (
                <button
                  type="button"
                  key={report.id}
                  onClick={() => setSelected(report)}
                  className={
                    selectedReport?.id === report.id
                      ? "intelligence-report-history-item intelligence-report-history-item-active"
                      : "intelligence-report-history-item"
                  }
                >
                  <strong>{report.title}</strong>
                  <span>{formatDateTime(report.generatedAt)}</span>
                  <small>
                    {titleCase(report.dataConfidence)} confidence ·{" "}
                    {report.aiStatus === "completed"
                      ? "AI narrative"
                      : "Verified only"}
                  </small>
                </button>
              ))}
            </div>
          ) : (
            <p className="intelligence-report-empty">
              No generated report yet. Create the first report above.
            </p>
          )}
        </aside>

        <main className="intelligence-report-preview">
          {selectedReport ? (
            <>
              <header className="intelligence-report-preview-head">
                <div>
                  <span>Verified management report</span>
                  <h3>{selectedReport.title}</h3>
                  <p>
                    {payload.period?.label || "Current position"} ·{" "}
                    {formatDateTime(selectedReport.generatedAt)}
                  </p>
                </div>

                <button type="button" onClick={handleDownload}>
                  <Download size={17} />
                  Download PDF
                </button>
              </header>

              <div className="intelligence-report-meta">
                <div>
                  <span>Confidence</span>
                  <strong>
                    {titleCase(selectedReport.dataConfidence)}
                  </strong>
                </div>
                <div>
                  <span>AI narrative</span>
                  <strong>{titleCase(selectedReport.aiStatus)}</strong>
                </div>
                <div>
                  <span>Generated by</span>
                  <strong>{selectedReport.generatedBy || "StockFlow"}</strong>
                </div>
              </div>

              <div className="intelligence-report-metrics">
                {(payload.metrics || []).map((metric) => (
                  <article key={metric.key}>
                    <span>{metric.label}</span>
                    <strong>
                      {formatValue(metric.value, metric.format)}
                    </strong>
                  </article>
                ))}
              </div>

              {selectedReport.aiNarrative ? (
                <article className="intelligence-report-ai-narrative">
                  <span>
                    <Sparkles size={15} />
                    AI management narrative
                  </span>
                  <p>{selectedReport.aiNarrative}</p>
                </article>
              ) : null}

              <div className="intelligence-report-questions">
                <QuestionBlock
                  title="What happened?"
                  items={questions.whatHappened}
                />
                <QuestionBlock
                  title="Why?"
                  items={questions.why}
                />
                <QuestionBlock
                  title="What needs attention?"
                  items={questions.attention}
                />
                <QuestionBlock
                  title="What should I do next?"
                  items={questions.nextActions}
                />
              </div>

              {sections.map((section) => (
                <section
                  className="intelligence-report-table-section"
                  key={section.key}
                >
                  <h4>{section.title}</h4>

                  {section.rows?.length ? (
                    <div className="intelligence-report-table-wrap">
                      <table>
                        <thead>
                          <tr>
                            {section.columns.map((column) => (
                              <th key={column.key}>{column.label}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {section.rows.map((row, index) => (
                            <tr key={`${section.key}-${index}`}>
                              {section.columns.map((column) => (
                                <td key={column.key}>
                                  {formatValue(
                                    row[column.key],
                                    column.format,
                                  )}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="intelligence-report-empty">
                      No matching records are currently active.
                    </p>
                  )}
                </section>
              ))}
            </>
          ) : (
            <div className="intelligence-report-preview-empty">
              <FileBarChart2 size={30} />
              <h3>No saved Intelligence report yet</h3>
              <p>
                Choose one of the seven management report types and generate
                a verified report.
              </p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
