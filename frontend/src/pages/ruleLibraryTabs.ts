export interface RuleLibraryTabSource {
  rules: unknown[];
  suggestions: unknown[];
  drafts: unknown[];
  changes: unknown[];
  templates: unknown[];
}

export interface RuleLibraryTabCounts {
  rules: number;
  suggestions: number;
  drafts: number;
  changes: number;
  templates: number;
}

export function getRuleLibraryTabCounts(source: RuleLibraryTabSource): RuleLibraryTabCounts {
  return {
    rules: source.rules.length,
    suggestions: source.suggestions.length,
    drafts: source.drafts.length,
    changes: source.changes.length,
    templates: source.templates.length,
  };
}
