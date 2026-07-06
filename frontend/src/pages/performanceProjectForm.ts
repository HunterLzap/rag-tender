import type { PerformanceProjectInput } from '../types';

export interface PerformanceProjectFormState {
  project_name: string;
  client_name: string;
  contract_no: string;
  contract_amount: string;
  sign_date: string;
  completion_date: string;
  project_scope: string;
  year: string;
  file_ids: number[];
  remark: string;
}

export const EMPTY_PERFORMANCE_PROJECT_FORM: PerformanceProjectFormState = {
  project_name: '',
  client_name: '',
  contract_no: '',
  contract_amount: '',
  sign_date: '',
  completion_date: '',
  project_scope: '',
  year: '',
  file_ids: [],
  remark: '',
};

const emptyToNull = (value: string): string | null => {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
};

export const buildPerformanceProjectPayload = (
  form: PerformanceProjectFormState,
): PerformanceProjectInput => ({
  project_name: form.project_name.trim(),
  client_name: emptyToNull(form.client_name),
  contract_no: emptyToNull(form.contract_no),
  contract_amount: emptyToNull(form.contract_amount),
  sign_date: emptyToNull(form.sign_date),
  completion_date: emptyToNull(form.completion_date),
  project_scope: emptyToNull(form.project_scope),
  year: emptyToNull(form.year),
  file_ids: form.file_ids,
  remark: emptyToNull(form.remark),
});
