/**
 * E5 L1 — behaviour thickness for HR / share preview.
 * Aggregates only; honest empty/thin states.
 */
import type { TimelineL1Summary } from "@looma/shared-core";

interface Props {
  summary?: TimelineL1Summary | null;
  className?: string;
}

export default function TimelineL1Card({ summary, className = "" }: Props) {
  const s = summary ?? {
    level: "l1",
    event_count: 0,
    has_thickness: false,
    confidence: "empty",
    message: "尚无足够行为沉淀，画像厚度不足",
    recent_labels: [],
  };

  const isEmpty = !s.has_thickness || s.confidence === "empty" || s.event_count === 0;
  const lastDay = (s.last_active_at || "").slice(0, 10);

  return (
    <div
      className={`rounded-xl p-5 mb-6 text-left ${className}`}
      style={{
        backgroundColor: "var(--color-bg-card)",
        boxShadow: "var(--shadow-sm)",
        border: isEmpty
          ? "1px dashed var(--color-border, rgba(0,0,0,0.12))"
          : "1px solid var(--color-border, rgba(0,0,0,0.08))",
      }}
    >
      <div className="flex items-center justify-between gap-2 mb-2">
        <h2 className="text-sm font-semibold m-0" style={{ color: "var(--color-text-primary)" }}>
          行为厚度 · L1
        </h2>
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {isEmpty ? "数据不足" : "初步可见"}
        </span>
      </div>

      <p className="text-xs leading-relaxed m-0 mb-3" style={{ color: "var(--color-text-secondary)" }}>
        {s.message}
      </p>

      {isEmpty ? (
        <div
          className="rounded-lg px-3 py-4 text-center text-xs"
          style={{ backgroundColor: "var(--color-bg-surface)", color: "var(--color-text-muted)" }}
        >
          尚无足够行为沉淀。人格结果仅为初始假设，不代表长期能力证明。
        </div>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-2 mb-3">
            <Stat label="行为节点" value={s.evidence_count ?? s.event_count} />
            <Stat label="项目记录" value={s.project_count ?? 0} />
            <Stat label="签到" value={s.check_in_count ?? 0} />
          </div>
          {s.recent_labels && s.recent_labels.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mb-2">
              {s.recent_labels.map((label) => (
                <span
                  key={label}
                  className="px-2 py-0.5 rounded-full text-xs"
                  style={{ backgroundColor: "var(--color-bg-surface)", color: "var(--color-text-secondary)" }}
                >
                  {label}
                </span>
              ))}
            </div>
          )}
          {lastDay && (
            <p className="text-xs m-0" style={{ color: "var(--color-text-muted)" }}>
              最近活跃 · {lastDay}
            </p>
          )}
          {s.hypothesis_present && (
            <p className="text-xs m-0 mt-2" style={{ color: "var(--color-text-muted)" }}>
              含人格冷启动假设，权重将随行为沉淀下降
            </p>
          )}
        </>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div
      className="rounded-lg px-2 py-2 text-center"
      style={{ backgroundColor: "var(--color-bg-surface)" }}
    >
      <div className="text-lg font-bold" style={{ color: "var(--color-primary)" }}>
        {value}
      </div>
      <div className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        {label}
      </div>
    </div>
  );
}
