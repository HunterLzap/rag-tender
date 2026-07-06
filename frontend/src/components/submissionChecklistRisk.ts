import type { SubmissionChecklist } from '../types';

export function isRedFlagChecklistItem(item: SubmissionChecklist): boolean {
  return Boolean(item.remark?.includes('【红线】'));
}
