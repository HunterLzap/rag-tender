export interface FileUploadCategoryOption {
  value: string;
  label: string;
}

const DEFAULT_FILE_UPLOAD_CATEGORY_OPTIONS: FileUploadCategoryOption[] = [
  { value: 'enterprise', label: '企业资质' },
  { value: 'personnel', label: '人员资质' },
  { value: 'financial', label: '财务' },
];

export const getDefaultFileUploadCategoryOptions = (): FileUploadCategoryOption[] =>
  DEFAULT_FILE_UPLOAD_CATEGORY_OPTIONS;
