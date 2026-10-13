// Friendly names for the generated API types. Regenerate schema.d.ts with `npm run gen:api`
// after changing the backend (python scripts/export_openapi.py first).
import type { components } from "./schema";

type S = components["schemas"];

export type User = S["UserRead"];
export type AssignableUser = S["AssignableUser"];
export type Role = S["Role"];
export type Transaction = S["TransactionRead"];
export type TransactionListItem = S["TransactionListItem"];
export type TransactionDetail = S["TransactionWithHistory"];
export type TransactionType = S["TransactionType"];
export type Assessment = S["RiskAssessmentRead"];
export type RuleHit = S["RuleHit"];
export type Alert = S["AlertRead"];
export type AlertDetail = S["AlertDetail"];
export type AlertStatus = S["AlertStatus"];
export type RiskLevel = S["RiskLevel"];
export type Case = S["CaseRead"];
export type CaseDetail = S["CaseDetail"];
export type CaseStatus = S["CaseStatus"];
export type CaseDecision = S["CaseDecision"];
export type Note = S["NoteRead"];
export type AuditEvent = S["AuditEventRead"];
export type Overview = S["Overview"];
export type RiskDistribution = S["RiskDistribution"];
export type ModelEvaluation = S["ModelEvaluation"];
export type ModelVersion = S["ModelVersionRead"];
export type Rule = S["RuleRead"];
export type ScoreOneResult = S["ScoreOneResult"];
export type TokenResponse = S["TokenResponse"];
export type ImportBatch = S["ImportBatchRead"];
export type ScoreRunResult = S["ScoreRunResult"];

export interface Page<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}
