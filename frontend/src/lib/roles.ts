import type { AlertStatus, Role, User } from "../api/types";

const RANK: Record<Role, number> = { analyst: 1, senior_analyst: 2, admin: 3 };

export function hasRole(user: Pick<User, "role"> | null | undefined, minimum: Role): boolean {
  return !!user && RANK[user.role] >= RANK[minimum];
}

// Mirrors backend/app/services/alerts.py. The server enforces it; the UI only hides buttons.
export const ALERT_TRANSITIONS: Record<AlertStatus, AlertStatus[]> = {
  open: ["in_review", "escalated", "closed_false_positive", "closed_actioned"],
  in_review: ["open", "escalated", "closed_false_positive", "closed_actioned"],
  escalated: ["in_review", "closed_false_positive", "closed_actioned"],
  closed_false_positive: ["in_review"],
  closed_actioned: ["in_review"],
};

const CLOSED: AlertStatus[] = ["closed_false_positive", "closed_actioned"];

export function allowedAlertMoves(
  status: AlertStatus,
  user: Pick<User, "id" | "role"> | null,
  assigneeId: number | null | undefined,
): AlertStatus[] {
  if (!user) return [];
  if (hasRole(user, "senior_analyst")) return ALERT_TRANSITIONS[status];
  if (assigneeId != null && assigneeId !== user.id) return [];
  if (CLOSED.includes(status) || status === "escalated") return [];
  return ALERT_TRANSITIONS[status];
}
