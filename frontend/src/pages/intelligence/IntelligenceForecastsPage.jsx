import {
  AlertTriangle,
  BarChart3,
  Boxes,
  RefreshCw,
  TrendingUp,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { useStore } from "../../context/StoreContext";
import { apiRequest } from "../../services/api";
import {
  formatCurrency,
  formatDate,
  formatDateTime,
  formatNumber,
  formatPercent,
  titleCase,
} from "./intelligenceUtils";


const HORIZONS = [7, 30, 90];


function ConfidencePill({ value }) {
  const normalized = String(value || "low").toLowerCase();

  return (
    <span
      className={
        "intelligence-status-pill " +
        `intelligence-status-${normalized}`
      }
    >
      {titleCase(normalized)}
    </span>
  );
}


export default function IntelligenceForecastsPage() {
  const { business } = useStore();
  const [horizon, setHorizon] = useState(30);
  const [forecast, setForecast] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");

  const loadForecast = useCallback(
    async (days) => {
      if (!business.id) return;

      setLoading(true);
      setError("");

      try {
        const history = await apiRequest(
          (
            `/businesses/${business.id}/intelligence/forecasts/` +
            `?horizonDays=${days}`
          ),
        );

        setForecast(
          Array.isArray(history) && history.length
            ? history[0]
            : null,
        );
      } catch (requestError) {
        setError(
          requestError.message ||
            "StockFlow could not load this forecast.",
        );
      } finally {
        setLoading(false);
      }
    },
    [business.id],
  );

  useEffect(() => {
    loadForecast(30);
  }, [loadForecast]);

  async function selectHorizon(days) {
    if (days === horizon || loading || generating) return;
    setHorizon(days);
    await loadForecast(days);
  }

  async function generateFreshForecast() {
    if (!business.id || generating) return;

    setGenerating(true);
    setError("");

    try {
      const created = await apiRequest(
        `/businesses/${business.id}/intelligence/forecasts/`,
        {
          method: "POST",
          body: JSON.stringify({
            horizonDays: horizon,
          }),
        },
      );
      setForecast(created);
    } catch (requestError) {
      setError(
        requestError.message ||
          "StockFlow could not generate a fresh forecast.",
      );
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div className="intelligence-page">
      <section className="intelligence-page-hero">
        <div>
          <span className="intelligence-eyebrow">
            <TrendingUp size={15} />
            Deterministic forecast engine
          </span>
          <h2>See what the verified sales history suggests next.</h2>
          <p>
            Forecasts use completed-day history, recent weighted demand,
            trend and confidence rather than an AI guess.
          </p>
        </div>

        <button
          type="button"
          className="intelligence-primary-action"
          onClick={generateFreshForecast}
          disabled={generating || loading}
        >
          <RefreshCw
            className={generating ? "intelligence-spin" : ""}
            size={16}
          />
          {generating ? "Generating..." : "Generate fresh forecast"}
        </button>
      </section>

      <div className="intelligence-horizon-tabs">
        {HORIZONS.map((days) => (
          <button
            type="button"
            key={days}
            onClick={() => selectHorizon(days)}
            disabled={loading || generating}
            className={
              horizon === days
                ? "intelligence-horizon-active"
                : ""
            }
          >
            {days} days
          </button>
        ))}
      </div>

      {error ? (
        <div className="intelligence-inline-error" role="alert">
          <AlertTriangle size={17} />
          <span>{error}</span>
        </div>
      ) : null}

      {loading ? (
        <div className="intelligence-state-card">
          <RefreshCw className="intelligence-spin" size={24} />
          <strong>Loading {horizon}-day forecast...</strong>
        </div>
      ) : null}

      {!loading && !forecast && !error ? (
        <div className="intelligence-state-card">
          <BarChart3 size={26} />
          <strong>No saved {horizon}-day forecast yet</strong>
          <span>
            Viewing this page does not create forecast records.
            Generate one explicitly when you want StockFlow to calculate
            and store a new forecast.
          </span>
          <button
            type="button"
            onClick={generateFreshForecast}
            disabled={generating}
          >
            {generating
              ? "Generating..."
              : `Generate ${horizon}-day forecast`}
          </button>
        </div>
      ) : null}

      {!loading && forecast ? (
        <>
          <section className="intelligence-confidence-card">
            <div>
              <span>Forecast confidence</span>
              <ConfidencePill value={forecast.confidence?.grade} />
            </div>
            <p>
              {forecast.confidence?.reason ||
                "Confidence evidence is not available."}
            </p>
            <small>
              Generated {formatDateTime(forecast.generatedAt)} ·
              History {formatDate(forecast.historyStart)} to{" "}
              {formatDate(forecast.historyEnd)}
            </small>
          </section>

          <section className="intelligence-metric-grid intelligence-forecast-metrics">
            <article className="intelligence-plain-metric">
              <BarChart3 size={20} />
              <span>Expected revenue</span>
              <strong>
                {formatCurrency(
                  forecast.businessForecast?.expectedRevenue,
                )}
              </strong>
            </article>

            <article className="intelligence-plain-metric">
              <TrendingUp size={20} />
              <span>Expected gross profit</span>
              <strong>
                {formatCurrency(
                  forecast.businessForecast?.expectedGrossProfit,
                )}
              </strong>
            </article>

            <article className="intelligence-plain-metric">
              <Boxes size={20} />
              <span>Expected quantity</span>
              <strong>
                {formatNumber(
                  forecast.businessForecast?.expectedQuantity,
                  2,
                )}
              </strong>
            </article>

            <article className="intelligence-plain-metric">
              <AlertTriangle size={20} />
              <span>Stock-out risks</span>
              <strong>
                {formatNumber(
                  forecast.businessForecast?.stockOutRiskCount,
                  0,
                )}
              </strong>
            </article>
          </section>

          <section className="intelligence-split-grid">
            <article className="intelligence-panel">
              <div className="intelligence-panel-heading">
                <div>
                  <span>Products</span>
                  <h3>Highest-priority product forecasts</h3>
                </div>
              </div>

              <div className="intelligence-list">
                {(forecast.productForecasts || [])
                  .slice(0, 10)
                  .map((item) => (
                    <div
                      className="intelligence-list-row intelligence-list-row-wide"
                      key={item.productId}
                    >
                      <div>
                        <strong>{item.name}</strong>
                        <span>
                          {item.sku} · {item.category}
                        </span>
                      </div>
                      <div>
                        <strong>
                          {formatCurrency(item.expectedRevenue)}
                        </strong>
                        <span>
                          {item.stockOutWithinHorizon
                            ? (
                                `${formatNumber(
                                  item.daysOfStockRemaining,
                                  1,
                                )} days stock`
                              )
                            : (
                                `${formatNumber(
                                  item.availableStock,
                                  0,
                                )} available`
                              )}
                        </span>
                        <ConfidencePill
                          value={item.confidenceGrade}
                        />
                      </div>
                    </div>
                  ))}
              </div>
            </article>

            <article className="intelligence-panel">
              <div className="intelligence-panel-heading">
                <div>
                  <span>Categories</span>
                  <h3>Expected category contribution</h3>
                </div>
              </div>

              <div className="intelligence-list">
                {(forecast.categoryForecasts || [])
                  .slice(0, 10)
                  .map((item) => (
                    <div
                      className="intelligence-list-row"
                      key={item.category}
                    >
                      <div>
                        <strong>{item.category}</strong>
                        <span>
                          {formatNumber(item.productCount, 0)} product(s)
                        </span>
                      </div>
                      <div>
                        <strong>
                          {formatCurrency(item.expectedRevenue)}
                        </strong>
                        <span>
                          {formatNumber(
                            item.stockOutRiskCount,
                            0,
                          )}{" "}
                          risk(s)
                        </span>
                      </div>
                    </div>
                  ))}
              </div>
            </article>
          </section>

          <details className="intelligence-methodology">
            <summary>Forecast methodology and evidence</summary>
            <div>
              <p>
                Algorithm: <strong>{forecast.algorithm}</strong>{" "}
                {forecast.algorithmVersion
                  ? `v${forecast.algorithmVersion}`
                  : ""}
              </p>
              <p>
                Historical margin:{" "}
                <strong>
                  {formatPercent(
                    forecast.businessForecast
                      ?.historicalMarginPercent,
                  )}
                </strong>
              </p>
              <p>
                Revenue direction:{" "}
                <strong>
                  {titleCase(
                    forecast.businessForecast?.revenueDirection,
                  )}
                </strong>
              </p>
              <p>
                Underlying data confidence:{" "}
                <strong>
                  {titleCase(
                    forecast.confidence?.dataGrade ||
                      forecast.confidence?.grade,
                  )}
                </strong>
              </p>
              <pre>
                {JSON.stringify(forecast.methodology || {}, null, 2)}
              </pre>
            </div>
          </details>
        </>
      ) : null}
    </div>
  );
}
