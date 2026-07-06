import type { Qualification } from '../types';

export interface QualificationExpiryDisplay {
  text: string;
  color: string;
}

export const getQualificationExpiryDisplay = (
  qualification: Pick<Qualification, 'expiry_date' | 'status'>,
  formatDate: (value: string) => string,
): QualificationExpiryDisplay => {
  if (qualification.status === 'needs_completion') {
    return { text: '待补全', color: '#F57C00' };
  }
  if (qualification.expiry_date) {
    return { text: formatDate(qualification.expiry_date), color: '#4CAF50' };
  }
  return { text: '长期有效', color: '#4CAF50' };
};
