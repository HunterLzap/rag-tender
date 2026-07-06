export function canSubmitMatchConfirmation(correctionReason: string): boolean {
  return correctionReason.trim().length > 0;
}
