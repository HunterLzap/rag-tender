export interface PaginationResult<T> {
  items: T[];
  page: number;
  pageCount: number;
  startIndex: number;
  endIndex: number;
  total: number;
}

export const clampPage = (
  page: number,
  total: number,
  pageSize: number,
): number => {
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  return Math.min(Math.max(1, page), pageCount);
};

export const paginateItems = <T>(
  items: T[],
  page: number,
  pageSize: number,
): PaginationResult<T> => {
  const validPage = clampPage(page, items.length, pageSize);
  const startIndex = (validPage - 1) * pageSize;
  const endIndex = Math.min(startIndex + pageSize, items.length);

  return {
    items: items.slice(startIndex, endIndex),
    page: validPage,
    pageCount: Math.max(1, Math.ceil(items.length / pageSize)),
    startIndex,
    endIndex,
    total: items.length,
  };
};
