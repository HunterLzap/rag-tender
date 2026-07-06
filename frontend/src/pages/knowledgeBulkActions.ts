import type { Qualification } from '../types';

export interface CurrentPageSelectionState {
  checked: boolean;
  indeterminate: boolean;
}

export interface BulkDeletePreview {
  sourceFileCount: number;
  manualQualificationCount: number;
  selectedQualificationCount: number;
}

export const toggleQualificationSelection = (
  selectedIds: Set<number>,
  qualificationId: number,
): Set<number> => {
  const next = new Set(selectedIds);
  if (next.has(qualificationId)) {
    next.delete(qualificationId);
  } else {
    next.add(qualificationId);
  }
  return next;
};

export const getCurrentPageSelectionState = (
  selectedIds: Set<number>,
  currentPageItems: Qualification[],
): CurrentPageSelectionState => {
  if (currentPageItems.length === 0) {
    return { checked: false, indeterminate: false };
  }
  const selectedCount = currentPageItems.filter((item) => selectedIds.has(item.id)).length;
  return {
    checked: selectedCount === currentPageItems.length,
    indeterminate: selectedCount > 0 && selectedCount < currentPageItems.length,
  };
};

export const toggleCurrentPageSelection = (
  selectedIds: Set<number>,
  currentPageItems: Qualification[],
): Set<number> => {
  const next = new Set(selectedIds);
  const state = getCurrentPageSelectionState(selectedIds, currentPageItems);
  for (const item of currentPageItems) {
    if (state.checked) {
      next.delete(item.id);
    } else {
      next.add(item.id);
    }
  }
  return next;
};

export const getBulkDeletePreview = (
  selectedQualifications: Qualification[],
): BulkDeletePreview => {
  const sourceFileIds = new Set(
    selectedQualifications
      .map((qualification) => qualification.file_id)
      .filter((fileId): fileId is number => fileId !== null),
  );
  const manualQualificationCount = selectedQualifications.filter(
    (qualification) => qualification.file_id === null,
  ).length;
  return {
    sourceFileCount: sourceFileIds.size,
    manualQualificationCount,
    selectedQualificationCount: selectedQualifications.length,
  };
};
