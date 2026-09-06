import {
  AlertTriangle,
  RefreshCw,
  ShieldCheck,
  WandSparkles,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { useStore } from "../../context/StoreContext";
import { apiRequest } from "../../services/api";
import {
  formatDateTime,
  titleCase,
} from "./intelligenceUtils";


function Pill({ value, prefix = "" }) {
  const normalized = String(value || "info").toLowerCase();

  return (
    <span
      className={
        "intelligence-status-pill " +
        `intelligence-status-${normalized}`
      }
    >
      {prefix}
      {titleCase(normalized)}
    </span>
  );
}


export default function IntelligenceRecommendationsPage() {
  const { business } = useStore();
  const [payload, setPayload] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");

  const loadRecommendations = useCallback(async () => {
    if (!business.id) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError("");

    try {
      const response = await apiRequest(
        `/businesses/${business.id}/intelligence/recommendations/`,
      );
      setPayload(response);
    } catch (requestError) {
      setError(
        requestError.message ||
          "StockFlow could not load active recommendations.",
      );
    } finally {
      setLoading(false);
    }
  }, [business.id]);

  useEffect(() => {
    loadRecommendations();
  }, [loadRecommendations]);

  async function generateRecommendations() {
    if (!business.id || generating) return;

    setGenerating(true);
    setError("");

    try {
      const response = await apiRequest(
        `/businesses/${business.id}/intelligence/recommendations/`,
        {
          method: "POST",
          body: JSON.stringify({}),
        },
      );
      setPayload(response);
    } catch (requestError) {
      setError(
        requestError.message ||
          "StockFlow could not generate recommendations.",
      );
    } finally {
      setGenerating(false);
    }
  }

  const recommendations = payload?.recommendations || [];

  return (
    <div className="intelligence-page">
      <section className="intelligence-page-hero">
        <div>
          <span className="intelligence-eyebrow">
            <WandSparkles size={15} />
            Explainable recommendations
          </span>
          <h2>Turn verified signals into clear next actions.</h2>
          <p>
            Recommendations remain advisory. StockFlow does not silently
            change stock, prices, sales, debt or payment records.
          </p>
        </div>

        <button
          type="button"
          className="intelligence-primary-action"
          onClick={generateRecommendations}
          disabled={generating || loading}
        >
          <RefreshCw
            className={generating ? "intelligence-spin" : ""}
            size={16}
          />
          {generating
            ? "Generating..."
            : recommendations.length
              ? "Refresh recommendations"
              : "Generate recommendations"}
        </button>
      </section>

      <section className="intelligence-safety-banner">
        <ShieldCheck size={19} />
        <div>
          <strong>Human confirmation remains required.</strong>
          <span>
            These recommendations explain what deserves attention; they
            do not execute consequential business actions.
          </span>
        </div>
      </section>

      {error ? (
        <div className="intelligence-inline-error" role="alert">
          <AlertTriangle size={17} />
          <span>{error}</span>
        </div>
      ) : null}

      {loading ? (
        <div className="intelligence-state-card">
          <RefreshCw className="intelligence-spin" size={24} />
          <strong>Loading active recommendations...</strong>
        </div>
      ) : null}

      {!loading && !recommendations.length ? (
        <div className="intelligence-state-card">
          <WandSparkles size={27} />
          <strong>No active recommendations yet</strong>
          <span>
            Generate recommendations when you want StockFlow to evaluate
            the latest verified overview and 30-day forecast.
          </span>
        </div>
      ) : null}

      {!loading && recommendations.length ? (
        <>
          <div className="intelligence-recommendation-summary">
            <span>
              {recommendations.length} active recommendation
              {recommendations.length === 1 ? "" : "s"}
            </span>
            <small>
              Generated {formatDateTime(payload.generatedAt)}
            </small>
          </div>

          <section className="intelligence-recommendation-grid">
            {recommendations.map((item) => (
              <article
                className={
                  "intelligence-recommendation-card " +
                  `intelligence-recommendation-${item.severity}`
                }
                key={item.id}
              >
                <div className="intelligence-recommendation-heading">
                  <div>
                    <span>{titleCase(item.insightType)}</span>
                    <h3>{item.title}</h3>
                  </div>

                  <div>
                    <Pill value={item.severity} />
                    <Pill
                      value={item.confidence}
                      prefix="Confidence: "
                    />
                  </div>
                </div>

                <p>{item.summary}</p>

                <details>
                  <summary>View supporting evidence</summary>
                  <pre>
                    {JSON.stringify(item.evidence || {}, null, 2)}
                  </pre>
                </details>
              </article>
            ))}
          </section>
        </>
      ) : null}
    </div>
  );
}
