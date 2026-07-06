export const shouldClearSelectedFiles = (
  previousClearKey: number | undefined,
  clearKey: number | undefined,
): boolean => {
  if (clearKey === undefined || previousClearKey === undefined) {
    return false;
  }
  return clearKey !== previousClearKey;
};
