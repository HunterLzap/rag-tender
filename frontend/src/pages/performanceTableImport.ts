import type { KnowledgeFile, PerformanceProject, PerformanceProjectInput } from '../types';

type ProjectField = keyof Pick<
  PerformanceProjectInput,
  | 'project_name'
  | 'client_name'
  | 'contract_no'
  | 'contract_amount'
  | 'sign_date'
  | 'completion_date'
  | 'project_scope'
  | 'year'
  | 'remark'
>;

export interface PerformanceTableParseResult {
  projects: PerformanceProjectInput[];
  errors: string[];
}

const HEADER_ALIASES: Record<string, ProjectField> = {
  项目名称: 'project_name',
  项目: 'project_name',
  业绩名称: 'project_name',
  甲方: 'client_name',
  客户: 'client_name',
  建设单位: 'client_name',
  发包方: 'client_name',
  合同编号: 'contract_no',
  合同号: 'contract_no',
  合同金额: 'contract_amount',
  金额: 'contract_amount',
  签订日期: 'sign_date',
  合同签订日期: 'sign_date',
  完成日期: 'completion_date',
  验收日期: 'completion_date',
  项目内容: 'project_scope',
  供货范围: 'project_scope',
  服务内容: 'project_scope',
  年度: 'year',
  所属年度: 'year',
  备注: 'remark',
};

const splitLine = (line: string): string[] => {
  if (line.includes('\t')) return line.split('\t');
  return line.split(',');
};

const clean = (value: string | null | undefined): string => (value || '').trim();

const normalizeMatchText = (value: string | null | undefined): string =>
  clean(value).toLocaleLowerCase().replace(/\s+/g, '');

const collectMatchTokens = (project: PerformanceProjectInput): string[] => {
  const tokens = [
    normalizeMatchText(project.contract_no),
    normalizeMatchText(project.project_name),
  ].filter((token) => token.length >= 2);
  return Array.from(new Set(tokens));
};

export const parsePerformanceProjectTable = (
  text: string,
): PerformanceTableParseResult => {
  const lines = text
    .split(/\r?\n/)
    .filter((line) => line.trim().length > 0);

  if (lines.length < 2) {
    return { projects: [], errors: ['请粘贴包含表头和至少一行数据的表格'] };
  }

  const headers = splitLine(lines[0]).map(clean);
  const fieldByIndex = headers.map((header) => HEADER_ALIASES[header]);
  if (!fieldByIndex.includes('project_name')) {
    return { projects: [], errors: ['表头缺少“项目名称/项目/业绩名称”列'] };
  }

  const projects: PerformanceProjectInput[] = [];
  for (const line of lines.slice(1)) {
    const cells = splitLine(line).map(clean);
    const project: PerformanceProjectInput = {
      project_name: '',
      file_ids: [],
    };
    fieldByIndex.forEach((field, index) => {
      if (!field) return;
      const value = clean(cells[index]);
      if (!value) return;
      project[field] = value;
    });
    if (project.project_name.trim()) {
      projects.push(project);
    }
  }

  if (projects.length === 0) {
    return { projects: [], errors: ['未解析到有效业绩项目'] };
  }
  return { projects, errors: [] };
};

export const attachPerformanceFilesToProjects = (
  projects: PerformanceProjectInput[],
  files: KnowledgeFile[],
): PerformanceProjectInput[] => {
  return projects.map((project) => {
    const tokens = collectMatchTokens(project);
    if (tokens.length === 0) return project;

    const matchedFileIds = files
      .filter((file) => {
        const filename = normalizeMatchText(file.filename);
        return tokens.some((token) => filename.includes(token));
      })
      .map((file) => file.id);

    return {
      ...project,
      file_ids: Array.from(new Set([...(project.file_ids || []), ...matchedFileIds])),
    };
  });
};

export const getUnlinkedPerformanceFiles = (
  files: KnowledgeFile[],
  projects: PerformanceProject[],
): KnowledgeFile[] => {
  const linkedFileIds = new Set(
    projects.flatMap((project) => project.file_ids),
  );
  return files.filter((file) => !linkedFileIds.has(file.id));
};
