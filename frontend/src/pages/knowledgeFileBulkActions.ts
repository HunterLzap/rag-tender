import type { KnowledgeFile } from '../types';

export interface CurrentPageFileSelectionState {
  checked: boolean;
  indeterminate: boolean;
}

export const toggleFileSelection = (
  selectedIds: Set<number>,
  fileId: number,
): Set<number> => {
  const next = new Set(selectedIds);
  if (next.has(fileId)) {
    next.delete(fileId);
  } else {
    next.add(fileId);
  }
  return next;
};

export const getCurrentPageFileSelectionState = (
  selectedIds: Set<number>,
  currentPageItems: KnowledgeFile[],
): CurrentPageFileSelectionState => {
  if (currentPageItems.length === 0) {
    return { checked: false, indeterminate: false };
  }
  const selectedCount = currentPageItems.filter((item) => selectedIds.has(item.id)).length;
  return {
    checked: selectedCount === currentPageItems.length,
    indeterminate: selectedCount > 0 && selectedCount < currentPageItems.length,
  };
};

export const toggleCurrentPageFileSelection = (
  selectedIds: Set<number>,
  currentPageItems: KnowledgeFile[],
): Set<number> => {
  const next = new Set(selectedIds);
  const state = getCurrentPageFileSelectionState(selectedIds, currentPageItems);
  for (const item of currentPageItems) {
    if (state.checked) {
      next.delete(item.id);
    } else {
      next.add(item.id);
    }
  }
  return next;
};
