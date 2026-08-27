import type { ConsensusStatus, FleetMatchResponse, MatchSpreadHint } from "../types/game";

export type MatchResultView = "verified" | "weak" | "failed";

export interface MatchUiState {
  view: MatchResultView;
  canComplete: boolean;
  threshold: number;
  spreadHint: MatchSpreadHint;
  statusLabel: string;
}

const DEFAULT_THRESHOLD = 85;
const WEAK_MIN_SCORE = 60;

function defaultSpreadHint(view: MatchResultView, canComplete: boolean): MatchSpreadHint {
  return {
    show_share_cta: !canComplete,
    message:
      view === "failed"
        ? "契合度未达共识阈值，邀请更多舰员扩大验证池"
        : view === "weak"
          ? "接近共振但未验证，分享信号拉更多人入舰队"
          : null,
    spread_count: 0,
    spread_target: 3,
  };
}

/** 从 match 响应推导三分流 UI 状态（后端字段优先，缺省时按分数推断 v0 兼容） */
export function deriveMatchUiState(data: FleetMatchResponse): MatchUiState {
  const score = data.match?.match_score ?? 0;
  const threshold = data.consensus_threshold ?? DEFAULT_THRESHOLD;
  const status = data.consensus_status;

  let view: MatchResultView;
  if (status === "consensus_verified") {
    view = "verified";
  } else if (status === "consensus_passed" || status === "consensus_weak") {
    view = "weak";
  } else if (status === "consensus_failed") {
    view = "failed";
  } else if (score >= threshold) {
    view = "verified";
  } else if (score >= WEAK_MIN_SCORE) {
    view = "weak";
  } else {
    view = "failed";
  }

  let canComplete = data.can_complete_mission;
  if (canComplete === undefined) {
    if (status === "consensus_verified") {
      canComplete = true;
    } else if (status === "consensus_passed" || status === "consensus_weak" || status === "consensus_failed") {
      canComplete = false;
    } else if (data.matched) {
      // v0：无共识字段时，只要匹配成功即可确认任务（不再卡死在 85 分）
      canComplete = true;
    } else {
      canComplete = score >= threshold;
    }
  }

  const spreadHint = data.spread_hint ?? defaultSpreadHint(view, canComplete);

  const statusLabel: Record<MatchResultView, string> = {
    verified: "共识共振达成",
    weak: "弱共振 · 待双向确认",
    failed: "未达共识阈值",
  };

  return { view, canComplete, threshold, spreadHint, statusLabel: statusLabel[view] };
}

export function consensusStatusLabel(status: ConsensusStatus): string {
  const labels: Record<ConsensusStatus, string> = {
    consensus_verified: "已验证",
    consensus_passed: "阈值通过",
    consensus_weak: "弱共振",
    consensus_failed: "未达标",
  };
  return labels[status];
}
