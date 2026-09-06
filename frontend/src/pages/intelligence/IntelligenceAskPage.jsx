import {
  AlertTriangle,
  Bot,
  BrainCircuit,
  Send,
  ShieldCheck,
  Sparkles,
  UserRound,
} from "lucide-react";
import { useMemo, useState } from "react";

import { useStore } from "../../context/StoreContext";
import { apiRequest } from "../../services/api";
import {
  formatDateTime,
  titleCase,
} from "./intelligenceUtils";


const STARTER_QUESTIONS = [
  "What happened in my business this week?",
  "Which products are likely to finish soon?",
  "Why is my profit changing?",
  "Which products are not moving?",
  "How much money is tied up in stock?",
];

const INTRO_MESSAGE = {
  id: "intro",
  role: "assistant",
  content:
    "Ask me about verified sales, profit, stock, debt, forecasts and recommendations. I will tell you when the evidence is not sufficient instead of guessing.",
};


function EvidenceSummary({ evidence, confidence, generatedAt }) {
  if (!evidence) return null;

  const horizons = evidence.availableForecastHorizons || [];

  return (
    <div className="intelligence-ask-evidence">
      <div>
        <span>Data confidence</span>
        <strong>{titleCase(confidence || "low")}</strong>
      </div>
      <div>
        <span>Saved forecasts</span>
        <strong>
          {horizons.length
            ? horizons.map((days) => `${days}d`).join(", ")
            : "None"}
        </strong>
      </div>
      <div>
        <span>Recommendations</span>
        <strong>{evidence.activeRecommendationCount ?? 0}</strong>
      </div>
      <div>
        <span>Answered</span>
        <strong>{formatDateTime(generatedAt)}</strong>
      </div>
    </div>
  );
}


export default function IntelligenceAskPage() {
  const { business } = useStore();
  const [messages, setMessages] = useState([INTRO_MESSAGE]);
  const [question, setQuestion] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);

  const conversationHistory = useMemo(
    () =>
      messages
        .filter((message) => message.id !== "intro")
        .slice(-6)
        .map((message) => ({
          role: message.role,
          content: message.content,
        })),
    [messages],
  );

  async function submitQuestion(value = question) {
    const trimmed = value.trim();

    if (!trimmed || sending || !business.id) return;

    setMessages((current) => [
      ...current,
      {
        id: `user-${Date.now()}`,
        role: "user",
        content: trimmed,
      },
    ]);
    setQuestion("");
    setError(null);
    setSending(true);

    try {
      const response = await apiRequest(
        `/businesses/${business.id}/intelligence/analyst/`,
        {
          method: "POST",
          body: JSON.stringify({
            question: trimmed,
            history: conversationHistory,
          }),
        },
      );

      setMessages((current) => [
        ...current,
        {
          id: `assistant-${Date.now()}`,
          role: "assistant",
          content: response.answer,
          evidence: response.evidence,
          confidence: response.confidence,
          generatedAt: response.generatedAt,
        },
      ]);
    } catch (requestError) {
      setError({
        code: requestError.data?.code || "analyst_unavailable",
        message:
          requestError.message ||
          "Ask StockFlow could not answer right now.",
      });
    } finally {
      setSending(false);
    }
  }

  function handleSubmit(event) {
    event.preventDefault();
    submitQuestion();
  }

  return (
    <div className="intelligence-page intelligence-ask-page">
      <section className="intelligence-page-hero">
        <div>
          <span className="intelligence-eyebrow">
            <Sparkles size={15} />
            Ask StockFlow AI
          </span>
          <h2>Ask questions grounded in verified business data.</h2>
          <p>
            Django calculates the figures. Ask StockFlow explains the
            verified context and tells you when evidence is insufficient.
          </p>
        </div>

        <div className="intelligence-ask-readonly">
          <ShieldCheck size={18} />
          <div>
            <strong>Read-only analyst</strong>
            <span>No business record can be changed from this chat.</span>
          </div>
        </div>
      </section>

      {error ? (
        <div className="intelligence-ask-error" role="alert">
          <AlertTriangle size={20} />
          <div>
            <strong>
              {error.code === "ai_not_configured"
                ? "Ask StockFlow needs AI configuration"
                : "Ask StockFlow is unavailable"}
            </strong>
            <span>{error.message}</span>
          </div>
        </div>
      ) : null}

      <section className="intelligence-ask-shell">
        <div className="intelligence-ask-starters">
          <span>Try asking</span>
          <div>
            {STARTER_QUESTIONS.map((starter) => (
              <button
                type="button"
                key={starter}
                onClick={() => submitQuestion(starter)}
                disabled={sending}
              >
                {starter}
              </button>
            ))}
          </div>
        </div>

        <div
          className="intelligence-ask-messages"
          aria-live="polite"
        >
          {messages.map((message) => {
            const isAssistant = message.role === "assistant";
            const Icon = isAssistant ? Bot : UserRound;

            return (
              <article
                key={message.id}
                className={
                  "intelligence-ask-message " +
                  (
                    isAssistant
                      ? "intelligence-ask-message-assistant"
                      : "intelligence-ask-message-user"
                  )
                }
              >
                <div className="intelligence-ask-message-icon">
                  <Icon size={18} />
                </div>

                <div className="intelligence-ask-message-body">
                  <div className="intelligence-ask-message-label">
                    <strong>
                      {isAssistant ? "Ask StockFlow" : "You"}
                    </strong>
                    {isAssistant && message.confidence ? (
                      <span>
                        {titleCase(message.confidence)} confidence
                      </span>
                    ) : null}
                  </div>

                  <p>{message.content}</p>

                  <EvidenceSummary
                    evidence={message.evidence}
                    confidence={message.confidence}
                    generatedAt={message.generatedAt}
                  />
                </div>
              </article>
            );
          })}

          {sending ? (
            <article className="intelligence-ask-message intelligence-ask-message-assistant">
              <div className="intelligence-ask-message-icon">
                <BrainCircuit
                  className="intelligence-spin"
                  size={18}
                />
              </div>
              <div className="intelligence-ask-message-body">
                <strong>Reading verified Intelligence context...</strong>
              </div>
            </article>
          ) : null}
        </div>

        <form
          className="intelligence-ask-composer"
          onSubmit={handleSubmit}
        >
          <textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Ask about sales, profit, stock, debt, forecasts or recommendations..."
            maxLength={800}
            rows={3}
            disabled={sending}
          />
          <div>
            <span>{question.length}/800</span>
            <button
              type="submit"
              disabled={!question.trim() || sending}
            >
              <Send size={17} />
              {sending ? "Thinking..." : "Ask StockFlow"}
            </button>
          </div>
        </form>
      </section>

      <p className="intelligence-ask-footnote">
        Authoritative figures always come from StockFlow backend
        Intelligence services.
      </p>
    </div>
  );
}
