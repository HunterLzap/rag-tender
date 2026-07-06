import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  Box,
  Paper,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tabs,
  Tab,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Divider,
  TextField,
  Select,
  MenuItem,
  Pagination,
  InputLabel,
  FormControl,
  IconButton,
  Chip,
  CircularProgress,
  Alert,
  Grid,
  Checkbox,
  OutlinedInput,
  Tooltip,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import VisibilityIcon from '@mui/icons-material/Visibility';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import DownloadIcon from '@mui/icons-material/Download';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import RefreshIcon from '@mui/icons-material/Refresh';
import FileUploader from '../components/FileUploader';
import {
  CategoryTag,
  StatusTag,
  type StatusKind,
} from '../components/StatusTags';
import { colors } from '../theme';
import {
  uploadFile,
  getFiles,
  getKnowledgeFilePreviewUrl,
  getFileStatus,
  deleteFile,
  reparseFile,
  getQualifications,
  createQualification,
  updateQualification,
  deleteQualification,
  bulkUpdateQualificationCategory,
  bulkDeleteQualificationsBySource,
  reparseIncompleteQualifications,
} from '../api/knowledge';
import {
  getPerformanceProjects,
  createPerformanceProject,
  updatePerformanceProject,
  deletePerformanceProject,
} from '../api/performance';
import type {
  KnowledgeFile,
  KnowledgeCategory,
  ParseStatus,
  Qualification,
  QualificationInput,
  PerformanceProject,
} from '../types';
import { paginateItems } from '../utils/pagination';
import {
  getDefaultKnowledgeCategory,
  getFinancialQualificationType,
  getFinancialTypeOptions,
  getPersonnelQualificationType,
  getPersonnelTypeOptions,
  getQualificationCategoryOptions,
  getQualificationColumns,
  getQualificationCellValue,
  summarizeFinancialQualifications,
  type DisplayQualification,
  type FinancialQualificationType,
  type PersonnelQualificationType,
} from './knowledgeQualificationColumns';
import {
  getBulkDeletePreview,
  getCurrentPageSelectionState,
  toggleCurrentPageSelection,
  toggleQualificationSelection,
} from './knowledgeBulkActions';
import {
  getCurrentPageFileSelectionState,
  toggleCurrentPageFileSelection,
  toggleFileSelection,
} from './knowledgeFileBulkActions';
import {
  EMPTY_PERFORMANCE_PROJECT_FORM,
  buildPerformanceProjectPayload,
  type PerformanceProjectFormState,
} from './performanceProjectForm';
import { getQualificationExpiryDisplay } from './qualificationDisplay';
import {
  attachPerformanceFilesToProjects,
  getUnlinkedPerformanceFiles,
  parsePerformanceProjectTable,
} from './performanceTableImport';

const PAGE_SIZE = 10;

/** Format an ISO datetime string to a localized display string. */
const formatDate = (iso: string | null): string => {
  if (!iso) return '—';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return '—';
  return d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
};

const CATEGORY_LABELS: Record<string, string> = {
  enterprise: '企业资质',
  personnel: '人员资质',
  performance: '业绩',
  financial: '财务',
  other: '其他',
};

const FILE_CATEGORY_TAG_LABELS: Record<KnowledgeCategory | 'other', string> = {
  enterprise: '企业资质',
  personnel: '人员资质',
  performance: '业绩',
  financial: '财务',
  other: '其他',
};

const middleEllipsis = (value: string, maxLength = 28): string => {
  if (value.length <= maxLength) return value;
  const ellipsis = '...';
  const keep = maxLength - ellipsis.length;
  const startLength = Math.ceil(keep / 2);
  const endLength = Math.floor(keep / 2);
  return `${value.slice(0, startLength)}${ellipsis}${value.slice(-endLength)}`;
};

const PARSE_STATUS_TAGS: Record<ParseStatus, { label: string; kind: StatusKind }> = {
  pending: { label: '待解析', kind: 'neutral' },
  parsing: { label: '解析中', kind: 'info' },
  completed: { label: '已完成', kind: 'success' },
  failed: { label: '失败', kind: 'error' },
};

type PreviewKind = 'pdf' | 'image' | 'unsupported';

const getFileExtension = (filename: string): string =>
  filename.split('.').pop()?.toLowerCase() || '';

const getPreviewKind = (file: KnowledgeFile): PreviewKind => {
  const ext = getFileExtension(file.filename);
  if (file.file_type === 'pdf' || ext === 'pdf') return 'pdf';
  if (
    file.file_type === 'image' ||
    ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp'].includes(ext)
  ) {
    return 'image';
  }
  return 'unsupported';
};

const buildPreviewUrl = (fileId: number, disposition: 'inline' | 'attachment' = 'inline') =>
  getKnowledgeFilePreviewUrl(fileId, disposition);

interface QualFormState {
  name: string;
  number: string;
  issue_date: string;
  expiry_date: string;
  issuing_authority: string;
  scope: string;
  level: string;
  holder: string;
  category: KnowledgeCategory | 'other';
}

const EMPTY_FORM: QualFormState = {
  name: '',
  number: '',
  issue_date: '',
  expiry_date: '',
  issuing_authority: '',
  scope: '',
  level: '',
  holder: '',
  category: 'enterprise',
};

/**
 * Knowledge base management page (route: /knowledge).
 * Two tabs: file list (upload + browse) and qualification list (CRUD).
 */
const KnowledgePage: React.FC = () => {
  const [activeTab, setActiveTab] = useState(0);
  const [files, setFiles] = useState<KnowledgeFile[]>([]);
  const [qualifications, setQualifications] = useState<Qualification[]>([]);
  const [performanceProjects, setPerformanceProjects] = useState<PerformanceProject[]>([]);
  const [qualCategory, setQualCategory] = useState<KnowledgeCategory | 'other'>(
    getDefaultKnowledgeCategory(),
  );
  const [personnelType, setPersonnelType] = useState<PersonnelQualificationType>('all');
  const [financialType, setFinancialType] = useState<FinancialQualificationType>('summary');
  const [filePage, setFilePage] = useState(1);
  const [qualificationPage, setQualificationPage] = useState(1);
  const [performanceProjectPage, setPerformanceProjectPage] = useState(1);
  const [uploaderClearKey, setUploaderClearKey] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Qualification form dialog state
  const [formOpen, setFormOpen] = useState(false);
  const [formMode, setFormMode] = useState<'add' | 'edit'>('add');
  const [formData, setFormData] = useState<QualFormState>(EMPTY_FORM);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [formSaving, setFormSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // Delete confirmation dialog state
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [selectedQualificationIds, setSelectedQualificationIds] = useState<Set<number>>(
    () => new Set(),
  );
  const [bulkCategoryOpen, setBulkCategoryOpen] = useState(false);
  const [bulkTargetCategory, setBulkTargetCategory] = useState<KnowledgeCategory | 'other'>(
    'enterprise',
  );
  const [bulkUpdatingCategory, setBulkUpdatingCategory] = useState(false);
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false);
  const [bulkDeleting, setBulkDeleting] = useState(false);
  const [reparsingIncomplete, setReparsingIncomplete] = useState(false);

  // File delete confirmation dialog state
  const [fileDeleteId, setFileDeleteId] = useState<number | null>(null);
  const [fileDeleting, setFileDeleting] = useState(false);
  const [selectedFileIds, setSelectedFileIds] = useState<Set<number>>(
    () => new Set(),
  );
  const [bulkFileDeleteOpen, setBulkFileDeleteOpen] = useState(false);
  const [bulkFileDeleting, setBulkFileDeleting] = useState(false);
  const [previewFile, setPreviewFile] = useState<KnowledgeFile | null>(null);

  // Performance project dialog state
  const [performanceFormOpen, setPerformanceFormOpen] = useState(false);
  const [performanceFormMode, setPerformanceFormMode] = useState<'add' | 'edit'>('add');
  const [performanceFormData, setPerformanceFormData] =
    useState<PerformanceProjectFormState>(EMPTY_PERFORMANCE_PROJECT_FORM);
  const [editingPerformanceId, setEditingPerformanceId] = useState<number | null>(null);
  const [performanceFormSaving, setPerformanceFormSaving] = useState(false);
  const [performanceFormError, setPerformanceFormError] = useState<string | null>(null);
  const [performanceDeleteId, setPerformanceDeleteId] = useState<number | null>(null);
  const [performanceDeleting, setPerformanceDeleting] = useState(false);
  const [performanceImportOpen, setPerformanceImportOpen] = useState(false);
  const [performanceImportText, setPerformanceImportText] = useState('');
  const [performanceImporting, setPerformanceImporting] = useState(false);
  const performanceUploadInputRef = useRef<HTMLInputElement>(null);

  const filePagination = useMemo(
    () => paginateItems(files, filePage, PAGE_SIZE),
    [filePage, files],
  );
  const displayedQualifications = useMemo(
    () => {
      if (qualCategory === 'personnel' && personnelType !== 'all') {
        return qualifications.filter(
          (qual) => getPersonnelQualificationType(qual) === personnelType,
        );
      }
      if (qualCategory === 'financial') {
        if (financialType === 'summary') {
          return summarizeFinancialQualifications(qualifications);
        }
        return qualifications.filter(
          (qual) => getFinancialQualificationType(qual) === financialType,
        );
      }
      return qualifications;
    },
    [financialType, personnelType, qualCategory, qualifications],
  );
  const qualificationPagination = useMemo(
    () => paginateItems(displayedQualifications, qualificationPage, PAGE_SIZE),
    [displayedQualifications, qualificationPage],
  );
  const performanceProjectPagination = useMemo(
    () => paginateItems(performanceProjects, performanceProjectPage, PAGE_SIZE),
    [performanceProjectPage, performanceProjects],
  );
  const qualificationColumns = useMemo(
    () => getQualificationColumns(qualCategory, personnelType, financialType),
    [financialType, personnelType, qualCategory],
  );
  const personnelTypeOptions = useMemo(
    () => getPersonnelTypeOptions(qualifications),
    [qualifications],
  );
  const financialTypeOptions = useMemo(
    () => getFinancialTypeOptions(qualifications),
    [qualifications],
  );
  const selectedQualifications = useMemo(
    () => qualifications.filter((qual) => selectedQualificationIds.has(qual.id)),
    [qualifications, selectedQualificationIds],
  );
  const currentPageSelectionState = useMemo(
    () => getCurrentPageSelectionState(
      selectedQualificationIds,
      qualificationPagination.items.filter((item) => !('sourceIds' in item)),
    ),
    [qualificationPagination.items, selectedQualificationIds],
  );
  const currentPageFileSelectionState = useMemo(
    () => getCurrentPageFileSelectionState(selectedFileIds, filePagination.items),
    [filePagination.items, selectedFileIds],
  );
  const bulkDeletePreview = useMemo(
    () => getBulkDeletePreview(selectedQualifications),
    [selectedQualifications],
  );
  const incompleteQualificationCount = useMemo(
    () => displayedQualifications.filter((qual) => qual.status === 'needs_completion').length,
    [displayedQualifications],
  );
  const performanceFiles = useMemo(
    () => files.filter((file) => file.category === 'performance'),
    [files],
  );
  const unlinkedPerformanceFiles = useMemo(
    () => getUnlinkedPerformanceFiles(performanceFiles, performanceProjects),
    [performanceFiles, performanceProjects],
  );
  const performanceImportResult = useMemo(
    () => {
      const result = parsePerformanceProjectTable(performanceImportText);
      return {
        ...result,
        projects: attachPerformanceFilesToProjects(result.projects, performanceFiles),
      };
    },
    [performanceFiles, performanceImportText],
  );
  const performanceImportMatchedFileCount = useMemo(
    () => performanceImportResult.projects.reduce(
      (total, project) => total + (project.file_ids?.length || 0),
      0,
    ),
    [performanceImportResult.projects],
  );
  const fileById = useMemo(
    () => new Map(files.map((file) => [file.id, file])),
    [files],
  );

  useEffect(() => {
    if (filePage !== filePagination.page) {
      setFilePage(filePagination.page);
    }
  }, [filePage, filePagination.page]);

  useEffect(() => {
    if (qualificationPage !== qualificationPagination.page) {
      setQualificationPage(qualificationPagination.page);
    }
  }, [qualificationPage, qualificationPagination.page]);

  useEffect(() => {
    if (qualCategory !== 'personnel' && personnelType !== 'all') {
      setPersonnelType('all');
    }
  }, [personnelType, qualCategory]);

  useEffect(() => {
    if (qualCategory !== 'financial' && financialType !== 'summary') {
      setFinancialType('summary');
    }
  }, [financialType, qualCategory]);

  useEffect(() => {
    if (performanceProjectPage !== performanceProjectPagination.page) {
      setPerformanceProjectPage(performanceProjectPagination.page);
    }
  }, [performanceProjectPage, performanceProjectPagination.page]);

  /** Load knowledge files from the backend. */
  const loadFiles = useCallback(async () => {
    try {
      const list = await getFiles();
      setFiles(list);
      setSelectedFileIds((prev) => {
        const validIds = new Set(list.map((file) => file.id));
        return new Set([...prev].filter((id) => validIds.has(id)));
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载文件列表失败');
    }
  }, []);

  /** Load qualifications, optionally filtered by category. */
  const loadQualifications = useCallback(async () => {
    try {
      const list = await getQualifications(qualCategory);
      setQualifications(list);
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载资质列表失败');
    }
  }, [qualCategory]);

  /** Load performance projects. */
  const loadPerformanceProjects = useCallback(async () => {
    try {
      const list = await getPerformanceProjects();
      setPerformanceProjects(list);
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载业绩项目失败');
    }
  }, []);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      setLoading(true);
      await Promise.all([loadFiles(), loadQualifications(), loadPerformanceProjects()]);
      if (mounted) setLoading(false);
    };
    load();
    return () => {
      mounted = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Reload qualifications when the category filter changes
  useEffect(() => {
    setQualificationPage(1);
    setSelectedQualificationIds(new Set());
    loadQualifications();
  }, [loadQualifications]);

  // Ref to latest loadQualifications (avoids re-triggering polling effect)
  const loadQualificationsRef = useRef(loadQualifications);
  loadQualificationsRef.current = loadQualifications;

  /**
   * Poll file parse status every 2 seconds while any file is pending/parsing.
   * When all files reach completed/failed, stop polling and refresh
   * the qualifications list so newly extracted records appear automatically.
   * Interval is cleaned up on unmount or when files change.
   */
  useEffect(() => {
    const hasPending = files.some(
      (f) => f.status === 'pending' || f.status === 'parsing'
    );
    if (!hasPending) return;

    const interval = setInterval(async () => {
      let anyChanged = false;
      let allDone = true;
      const updatedFiles = [...files];

      for (let i = 0; i < updatedFiles.length; i++) {
        const f = updatedFiles[i];
        if (f.status === 'pending' || f.status === 'parsing') {
          try {
            const result = await getFileStatus(f.id);
            if (result.status !== f.status) {
              updatedFiles[i] = { ...f, status: result.status };
              anyChanged = true;
            }
            if (result.status === 'pending' || result.status === 'parsing') {
              allDone = false;
            }
          } catch {
            // Network error for individual file — keep polling
            allDone = false;
          }
        }
      }

      if (anyChanged) {
        setFiles(updatedFiles);
      }

      if (allDone) {
        clearInterval(interval);
        await loadQualificationsRef.current();
        await loadPerformanceProjects();
        setUploaderClearKey((prev) => prev + 1);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [files, loadPerformanceProjects]);

  /** Handle knowledge file upload. */
  const handleFilesSelected = useCallback(
    async (selectedFiles: File[], category?: string) => {
      if (selectedFiles.length === 0 || !category) return;
      setUploading(true);
      setError(null);
      try {
        for (const file of selectedFiles) {
          await uploadFile(file, category);
        }
        await loadFiles();
      } catch (err) {
        setError(err instanceof Error ? err.message : '上传文件失败');
      } finally {
        setUploading(false);
      }
    },
    [loadFiles]
  );

  const handlePerformanceUploadChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const selectedFiles = Array.from(event.target.files || []);
      event.target.value = '';
      void handleFilesSelected(selectedFiles, 'performance');
    },
    [handleFilesSelected],
  );

  /** Open the qualification form dialog in "add" mode. */
  const handleAddClick = useCallback(() => {
    setFormMode('add');
    setFormData(EMPTY_FORM);
    setEditingId(null);
    setFormError(null);
    setFormOpen(true);
  }, []);

  /** Open the qualification form dialog in "edit" mode. */
  const handleEditClick = useCallback((qual: Qualification) => {
    setFormMode('edit');
    setFormData({
      name: qual.name,
      number: qual.number,
      issue_date: qual.issue_date || '',
      expiry_date: qual.expiry_date || '',
      issuing_authority: qual.issuing_authority,
      scope: qual.scope,
      level: qual.level,
      holder: qual.holder,
      category: qual.category,
    });
    setEditingId(qual.id);
    setFormError(null);
    setFormOpen(true);
  }, []);

  /** Save (create or update) the qualification form. */
  const handleFormSubmit = useCallback(async () => {
    if (!formData.name.trim() || !formData.number.trim()) {
      setFormError('名称和编号为必填项');
      return;
    }
    setFormSaving(true);
    setFormError(null);
    try {
      const payload: QualificationInput = {
        name: formData.name,
        number: formData.number,
        issue_date: formData.issue_date || null,
        expiry_date: formData.expiry_date || null,
        issuing_authority: formData.issuing_authority,
        scope: formData.scope,
        level: formData.level,
        holder: formData.holder,
        category: formData.category,
      };
      if (formMode === 'edit' && editingId !== null) {
        await updateQualification(editingId, payload);
      } else {
        await createQualification(payload);
      }
      setFormOpen(false);
      await loadQualifications();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : '保存失败');
    } finally {
      setFormSaving(false);
    }
  }, [formData, formMode, editingId, loadQualifications]);

  /** Confirm deletion of a qualification. */
  const handleDeleteConfirm = useCallback(async () => {
    if (deleteId === null) return;
    setDeleting(true);
    try {
      await deleteQualification(deleteId);
      setDeleteId(null);
      await loadQualifications();
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除失败');
    } finally {
      setDeleting(false);
    }
  }, [deleteId, loadQualifications]);

  const handleToggleQualification = useCallback((qualificationId: number) => {
    setSelectedQualificationIds((prev) =>
      toggleQualificationSelection(prev, qualificationId)
    );
  }, []);

  const handleToggleCurrentPageQualifications = useCallback(() => {
    setSelectedQualificationIds((prev) =>
      toggleCurrentPageSelection(
        prev,
        qualificationPagination.items.filter((item) => !('sourceIds' in item)),
      )
    );
  }, [qualificationPagination.items]);

  const handleBulkCategoryConfirm = useCallback(async () => {
    const ids = [...selectedQualificationIds];
    if (ids.length === 0) return;
    setBulkUpdatingCategory(true);
    try {
      await bulkUpdateQualificationCategory(ids, bulkTargetCategory);
      setBulkCategoryOpen(false);
      setSelectedQualificationIds(new Set());
      await Promise.all([loadFiles(), loadQualifications()]);
    } catch (err) {
      setError(err instanceof Error ? err.message : '批量修改分类失败');
    } finally {
      setBulkUpdatingCategory(false);
    }
  }, [
    bulkTargetCategory,
    loadFiles,
    loadQualifications,
    selectedQualificationIds,
  ]);

  const handleBulkDeleteConfirm = useCallback(async () => {
    const ids = [...selectedQualificationIds];
    if (ids.length === 0) return;
    setBulkDeleting(true);
    try {
      await bulkDeleteQualificationsBySource(ids);
      setBulkDeleteOpen(false);
      setSelectedQualificationIds(new Set());
      await Promise.all([loadFiles(), loadQualifications()]);
    } catch (err) {
      setError(err instanceof Error ? err.message : '批量删除失败');
    } finally {
      setBulkDeleting(false);
    }
  }, [loadFiles, loadQualifications, selectedQualificationIds]);

  /** Update a single field in the qualification form. */
  const handleFieldChange = useCallback(
    (field: keyof QualFormState, value: string) => {
      setFormData((prev) => ({ ...prev, [field]: value }));
    },
    []
  );

  /** Open the file delete confirmation dialog. */
  const handleFileDeleteClick = useCallback((fileId: number) => {
    setFileDeleteId(fileId);
  }, []);

  /** Confirm deletion of a knowledge file (also deletes associated qualifications). */
  const handleFileDeleteConfirm = useCallback(async () => {
    if (fileDeleteId === null) return;
    setFileDeleting(true);
    try {
      await deleteFile(fileDeleteId);
      await Promise.all([loadFiles(), loadQualifications()]);
      setFileDeleteId(null);
      setSelectedFileIds((prev) => {
        const next = new Set(prev);
        next.delete(fileDeleteId);
        return next;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除文件失败');
    } finally {
      setFileDeleting(false);
    }
  }, [fileDeleteId, loadFiles, loadQualifications]);

  const handleToggleFile = useCallback((fileId: number) => {
    setSelectedFileIds((prev) => toggleFileSelection(prev, fileId));
  }, []);

  const handleToggleCurrentPageFiles = useCallback(() => {
    setSelectedFileIds((prev) =>
      toggleCurrentPageFileSelection(prev, filePagination.items)
    );
  }, [filePagination.items]);

  const handleBulkFileDeleteConfirm = useCallback(async () => {
    const ids = [...selectedFileIds];
    if (ids.length === 0) return;
    setBulkFileDeleting(true);
    try {
      for (const fileId of ids) {
        await deleteFile(fileId);
      }
      setBulkFileDeleteOpen(false);
      setSelectedFileIds(new Set());
      await Promise.all([loadFiles(), loadQualifications()]);
    } catch (err) {
      setError(err instanceof Error ? err.message : '批量删除文件失败');
    } finally {
      setBulkFileDeleting(false);
    }
  }, [loadFiles, loadQualifications, selectedFileIds]);

  const handleAddPerformanceClick = useCallback(() => {
    setPerformanceFormMode('add');
    setPerformanceFormData(EMPTY_PERFORMANCE_PROJECT_FORM);
    setEditingPerformanceId(null);
    setPerformanceFormError(null);
    setPerformanceFormOpen(true);
  }, []);

  const handleEditPerformanceClick = useCallback((project: PerformanceProject) => {
    setPerformanceFormMode('edit');
    setPerformanceFormData({
      project_name: project.project_name || '',
      client_name: project.client_name || '',
      contract_no: project.contract_no || '',
      contract_amount: project.contract_amount || '',
      sign_date: project.sign_date || '',
      completion_date: project.completion_date || '',
      project_scope: project.project_scope || '',
      year: project.year || '',
      file_ids: project.file_ids || [],
      remark: project.remark || '',
    });
    setEditingPerformanceId(project.id);
    setPerformanceFormError(null);
    setPerformanceFormOpen(true);
  }, []);

  const handlePerformanceFieldChange = useCallback(
    (field: keyof PerformanceProjectFormState, value: string | number[]) => {
      setPerformanceFormData((prev) => ({ ...prev, [field]: value }));
    },
    [],
  );

  const handlePerformanceFormSubmit = useCallback(async () => {
    if (!performanceFormData.project_name.trim()) {
      setPerformanceFormError('项目名称为必填项');
      return;
    }
    setPerformanceFormSaving(true);
    setPerformanceFormError(null);
    try {
      const payload = buildPerformanceProjectPayload(performanceFormData);
      if (performanceFormMode === 'edit' && editingPerformanceId !== null) {
        await updatePerformanceProject(editingPerformanceId, payload);
      } else {
        await createPerformanceProject(payload);
      }
      setPerformanceFormOpen(false);
      await loadPerformanceProjects();
    } catch (err) {
      setPerformanceFormError(err instanceof Error ? err.message : '保存业绩项目失败');
    } finally {
      setPerformanceFormSaving(false);
    }
  }, [
    editingPerformanceId,
    loadPerformanceProjects,
    performanceFormData,
    performanceFormMode,
  ]);

  const handlePerformanceDeleteConfirm = useCallback(async () => {
    if (performanceDeleteId === null) return;
    setPerformanceDeleting(true);
    try {
      await deletePerformanceProject(performanceDeleteId);
      setPerformanceDeleteId(null);
      await loadPerformanceProjects();
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除业绩项目失败');
    } finally {
      setPerformanceDeleting(false);
    }
  }, [loadPerformanceProjects, performanceDeleteId]);

  const handlePerformanceImportConfirm = useCallback(async () => {
    if (performanceImportResult.projects.length === 0) return;
    setPerformanceImporting(true);
    try {
      for (const project of performanceImportResult.projects) {
        await createPerformanceProject(project);
      }
      setPerformanceImportOpen(false);
      setPerformanceImportText('');
      await loadPerformanceProjects();
    } catch (err) {
      setError(err instanceof Error ? err.message : '批量导入业绩项目失败');
    } finally {
      setPerformanceImporting(false);
    }
  }, [loadPerformanceProjects, performanceImportResult.projects]);

  /** Trigger re-parsing of a knowledge file. */
  const handleReparseClick = useCallback(async (fileId: number) => {
    try {
      await reparseFile(fileId);
      await loadFiles();
    } catch (err) {
      setError(err instanceof Error ? err.message : '重新解析失败');
    }
  }, [loadFiles]);

  const handleReparseIncompleteClick = useCallback(async () => {
    setReparsingIncomplete(true);
    setError(null);
    try {
      if (qualCategory === 'personnel' && personnelType !== 'all') {
        const fileIds = Array.from(new Set(
          displayedQualifications
            .filter((qual) => qual.status === 'needs_completion' && qual.file_id !== null)
            .map((qual) => qual.file_id as number),
        ));
        for (const fileId of fileIds) {
          await reparseFile(fileId);
        }
      } else {
        await reparseIncompleteQualifications(qualCategory);
      }
      await Promise.all([loadFiles(), loadQualifications()]);
    } catch (err) {
      setError(err instanceof Error ? err.message : '一键分析待补全失败');
    } finally {
      setReparsingIncomplete(false);
    }
  }, [displayedQualifications, loadFiles, loadQualifications, personnelType, qualCategory]);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
        <CircularProgress sx={{ color: '#7C4DFF' }} />
      </Box>
    );
  }

  return (
    <Box>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 2,
          mb: 2,
        }}
      >
        <Typography variant="h2" sx={{ color: '#333' }}>
          资质库
        </Typography>
      </Box>

      <Tabs
        value={activeTab}
        onChange={(_, value: number) => setActiveTab(value)}
        sx={{
          borderBottom: 1,
          borderColor: '#EDE7F6',
          mb: 3,
          '& .Mui-selected': { color: '#7C4DFF' },
          '& .MuiTabs-indicator': { backgroundColor: '#7C4DFF' },
        }}
      >
        <Tab label="文件列表" />
        <Tab label="资质列表" />
        <Tab label="业绩项目" />
      </Tabs>

      {/* ===== Tab 0: File list ===== */}
      {activeTab === 0 && (
        <Box>
          <Paper
            sx={{
              p: 3,
              mb: 3,
              backgroundColor: '#FFFFFF',
              border: '1px solid #EDE7F6',
              borderRadius: 2,
            }}
          >
            <Typography variant="h6" sx={{ color: '#333', fontWeight: 600, mb: 2 }}>
              上传资质库文件
            </Typography>
            <FileUploader
              accept=".pdf,.docx,.doc,.xlsx,.xls,.jpg,.png"
              showCategory
              multiple
              onFilesSelected={handleFilesSelected}
              uploading={uploading}
              clearKey={uploaderClearKey}
            />
          </Paper>

          <Paper
            sx={{
              backgroundColor: '#FFFFFF',
              border: '1px solid #EDE7F6',
              borderRadius: 2,
              overflow: 'hidden',
            }}
          >
            <Box sx={{ p: 2 }}>
              <Typography variant="h6" sx={{ color: '#333', fontWeight: 600 }}>
                已上传文件
              </Typography>
            </Box>
            {selectedFileIds.size > 0 && (
              <Box
                sx={{
                  mx: 2,
                  mb: 2,
                  p: 1.5,
                  border: '1px solid #EDE7F6',
                  borderRadius: 1.5,
                  backgroundColor: '#FBF9FF',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 2,
                  flexWrap: 'wrap',
                }}
              >
                <Typography variant="body2" sx={{ color: '#555', fontWeight: 600 }}>
                  已选择 {selectedFileIds.size} 个文件
                </Typography>
                <Box sx={{ display: 'flex', gap: 1 }}>
                  <Button
                    size="small"
                    variant="outlined"
                    onClick={() => setBulkFileDeleteOpen(true)}
                    sx={{
                      borderColor: '#EF5350',
                      color: '#EF5350',
                      '&:hover': { borderColor: '#D32F2F', backgroundColor: '#FFF5F5' },
                    }}
                  >
                    批量删除
                  </Button>
                  <Button
                    size="small"
                    onClick={() => setSelectedFileIds(new Set())}
                    sx={{ color: '#777' }}
                  >
                    取消选择
                  </Button>
                </Box>
              </Box>
            )}
            {files.length === 0 ? (
              <Typography
                variant="body2"
                sx={{ color: '#999', py: 4, textAlign: 'center' }}
              >
                暂无文件，请上传资质库文件
              </Typography>
            ) : (
              <TableContainer>
                <Table size="small" sx={{ tableLayout: 'fixed' }}>
                  <TableHead>
                    <TableRow>
                      <TableCell padding="checkbox" sx={{ width: 44 }}>
                        <Checkbox
                          checked={currentPageFileSelectionState.checked}
                          indeterminate={currentPageFileSelectionState.indeterminate}
                          onChange={handleToggleCurrentPageFiles}
                          size="small"
                          sx={{ color: '#7C4DFF', '&.Mui-checked': { color: '#7C4DFF' } }}
                        />
                      </TableCell>
                      <TableCell sx={{ width: '38%' }}>文件名</TableCell>
                      <TableCell sx={{ width: '12%' }}>分类</TableCell>
                      <TableCell sx={{ width: '18%' }}>状态</TableCell>
                      <TableCell sx={{ width: '18%' }}>上传时间</TableCell>
                      <TableCell sx={{ width: '14%', textAlign: 'right' }}>操作</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {filePagination.items.map((file) => {
                      const statusCfg = PARSE_STATUS_TAGS[file.status] || PARSE_STATUS_TAGS.pending;
                      const isParsing =
                        file.status === 'pending' || file.status === 'parsing';
                      const isFailed = file.status === 'failed';
                      return (
                        <TableRow
                          key={file.id}
                          hover
                          className="zebra"
                          sx={{
                            height: 40,
                            ...(isFailed
                              ? {
                                  '& .MuiTableCell-root': {
                                    backgroundColor: colors.status.errorBg,
                                  },
                                }
                              : {}),
                          }}
                        >
                          <TableCell padding="checkbox">
                            <Checkbox
                              checked={selectedFileIds.has(file.id)}
                              onChange={() => handleToggleFile(file.id)}
                              size="small"
                              sx={{ color: '#7C4DFF', '&.Mui-checked': { color: '#7C4DFF' } }}
                            />
                          </TableCell>
                          <TableCell>
                            <Tooltip title={file.filename} arrow placement="top-start">
                              <Typography
                                variant="body2"
                                sx={{
                                  color: 'text.primary',
                                  fontWeight: 600,
                                  overflow: 'hidden',
                                  textOverflow: 'ellipsis',
                                  whiteSpace: 'nowrap',
                                  cursor: 'default',
                                }}
                              >
                                {middleEllipsis(file.filename)}
                              </Typography>
                            </Tooltip>
                            <Typography variant="caption" color="text.secondary">
                              {file.file_type || getFileExtension(file.filename)}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Tooltip title={CATEGORY_LABELS[file.category] || file.category} arrow>
                              <Box component="span">
                                <CategoryTag category={FILE_CATEGORY_TAG_LABELS[file.category]} />
                              </Box>
                            </Tooltip>
                          </TableCell>
                          <TableCell>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
                              {isParsing && (
                                <CircularProgress size={14} sx={{ color: '#1976D2' }} />
                              )}
                              <StatusTag kind={statusCfg.kind} label={statusCfg.label} />
                              {isParsing && (
                                <Typography
                                  variant="caption"
                                  sx={{ color: '#1976D2', fontSize: 11 }}
                                >
                                  解析中...
                                </Typography>
                              )}
                              {isFailed && (
                                <Typography
                                  variant="caption"
                                  sx={{ color: '#EF5350', fontSize: 11 }}
                                >
                                  解析失败
                                </Typography>
                              )}
                            </Box>
                          </TableCell>
                          <TableCell sx={{ color: '#666' }}>
                            {formatDate(file.upload_time)}
                          </TableCell>
                          <TableCell sx={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 0.5 }}>
                              <Tooltip title="查看文件">
                                <IconButton
                                  size="small"
                                  onClick={() => setPreviewFile(file)}
                                  sx={{ color: 'text.secondary' }}
                                >
                                  <VisibilityIcon fontSize="small" />
                                </IconButton>
                              </Tooltip>
                            {!isParsing && (
                              <>
                                <Tooltip title={isFailed ? '重试解析' : '重新解析'}>
                                  <IconButton
                                    size="small"
                                    onClick={() => handleReparseClick(file.id)}
                                    sx={{ color: 'primary.main' }}
                                  >
                                    <RefreshIcon fontSize="small" />
                                  </IconButton>
                                </Tooltip>
                                <Divider
                                  orientation="vertical"
                                  flexItem
                                  sx={{ mx: 0.5, height: 16, alignSelf: 'center' }}
                                />
                                <Tooltip title="删除">
                                <IconButton
                                  size="small"
                                  onClick={() => handleFileDeleteClick(file.id)}
                                  sx={{
                                    color: 'text.secondary',
                                    '&:hover': {
                                      color: 'error.main',
                                      backgroundColor: colors.status.errorBg,
                                    },
                                  }}
                                >
                                  <DeleteIcon fontSize="small" />
                                </IconButton>
                                </Tooltip>
                              </>
                            )}
                            </Box>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
            {files.length > 0 && (
              <PaginationFooter
                page={filePagination.page}
                pageCount={filePagination.pageCount}
                startIndex={filePagination.startIndex}
                endIndex={filePagination.endIndex}
                total={filePagination.total}
                onPageChange={setFilePage}
              />
            )}
          </Paper>
        </Box>
      )}

      {/* ===== Tab 1: Qualification list ===== */}
      {activeTab === 1 && (
        <Box>
          {/* Toolbar: add button + category filter */}
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap' }}>
              <FormControl size="small" sx={{ minWidth: 180 }}>
                <InputLabel>分类筛选</InputLabel>
                <Select
                  value={qualCategory}
                  label="分类筛选"
                  onChange={(e) => {
                    setQualCategory(e.target.value as KnowledgeCategory | 'other');
                    setQualificationPage(1);
                  }}
                >
                  {getQualificationCategoryOptions().map((opt) => (
                    <MenuItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              {qualCategory === 'personnel' && (
                <FormControl size="small" sx={{ minWidth: 190 }}>
                  <InputLabel>资料类型</InputLabel>
                  <Select
                    value={personnelType}
                    label="资料类型"
                    onChange={(e) => {
                      setPersonnelType(e.target.value as PersonnelQualificationType);
                      setQualificationPage(1);
                    }}
                  >
                    {personnelTypeOptions.map((opt) => (
                      <MenuItem key={opt.value} value={opt.value}>
                        {opt.label}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              )}
              {qualCategory === 'financial' && (
                <FormControl size="small" sx={{ minWidth: 210 }}>
                  <InputLabel>资料类型</InputLabel>
                  <Select
                    value={financialType}
                    label="资料类型"
                    onChange={(e) => {
                      setFinancialType(e.target.value as FinancialQualificationType);
                      setQualificationPage(1);
                    }}
                  >
                    {financialTypeOptions.map((opt) => (
                      <MenuItem key={opt.value} value={opt.value}>
                        {opt.label}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              )}
            </Box>
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={handleAddClick}
              sx={{
                backgroundColor: '#7C4DFF',
                '&:hover': { backgroundColor: '#651FFF' },
              }}
            >
              手动新增资质
            </Button>
          </Box>

          {incompleteQualificationCount > 0 && (
            <Alert
              severity="warning"
              sx={{ mb: 2 }}
              action={
                <Button
                  color="inherit"
                  size="small"
                  onClick={handleReparseIncompleteClick}
                  disabled={reparsingIncomplete}
                >
                  {reparsingIncomplete ? '分析中...' : '一键分析待补全'}
                </Button>
              }
            >
              当前分类有 {incompleteQualificationCount} 条待补全记录。可一键重新分析源文件，能自动识别的会自动更新。
            </Alert>
          )}

          {qualCategory === 'financial' && financialType === 'summary' && (
            <Alert severity="info" sx={{ mb: 2 }}>
              财务资料默认按“资料类型 + 主体 + 出具机构”汇总展示，避免同类纳税/完税证明刷屏。
              如需逐份编辑或删除，请在“资料类型”中切换到对应明细。
            </Alert>
          )}

          {selectedQualificationIds.size > 0 && (
            <Paper
              sx={{
                mb: 2,
                p: 1.5,
                border: '1px solid #EDE7F6',
                backgroundColor: '#FBF9FF',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 2,
                flexWrap: 'wrap',
              }}
            >
              <Typography variant="body2" sx={{ color: '#555', fontWeight: 600 }}>
                已选择 {selectedQualificationIds.size} 项
              </Typography>
              <Box sx={{ display: 'flex', gap: 1 }}>
                <Button
                  size="small"
                  variant="outlined"
                  onClick={() => {
                    setBulkTargetCategory(qualCategory);
                    setBulkCategoryOpen(true);
                  }}
                  sx={{
                    borderColor: '#7C4DFF',
                    color: '#7C4DFF',
                    '&:hover': { borderColor: '#651FFF', backgroundColor: '#F4EEFF' },
                  }}
                >
                  批量改分类
                </Button>
                <Button
                  size="small"
                  variant="outlined"
                  onClick={() => setBulkDeleteOpen(true)}
                  sx={{
                    borderColor: '#EF5350',
                    color: '#EF5350',
                    '&:hover': { borderColor: '#D32F2F', backgroundColor: '#FFF5F5' },
                  }}
                >
                  批量删除
                </Button>
                <Button
                  size="small"
                  onClick={() => setSelectedQualificationIds(new Set())}
                  sx={{ color: '#777' }}
                >
                  取消选择
                </Button>
              </Box>
            </Paper>
          )}

          <Paper
            sx={{
              backgroundColor: '#FFFFFF',
              border: '1px solid #EDE7F6',
              borderRadius: 2,
              overflow: 'hidden',
            }}
          >
            {displayedQualifications.length === 0 ? (
              <Typography
                variant="body2"
                sx={{ color: '#999', py: 4, textAlign: 'center' }}
              >
                暂无资质记录，请上传文件或手动新增
              </Typography>
            ) : (
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow sx={{ backgroundColor: '#F9F7FF' }}>
                      <TableCell padding="checkbox">
                        <Checkbox
                          checked={currentPageSelectionState.checked}
                          indeterminate={currentPageSelectionState.indeterminate}
                          onChange={handleToggleCurrentPageQualifications}
                          size="small"
                          sx={{ color: '#7C4DFF', '&.Mui-checked': { color: '#7C4DFF' } }}
                        />
                      </TableCell>
                      {qualificationColumns.map((column) => (
                        <TableCell key={column.key} sx={{ fontWeight: 600, color: '#666' }}>
                          {column.label}
                        </TableCell>
                      ))}
                      <TableCell sx={{ fontWeight: 600, color: '#666' }}>操作</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {qualificationPagination.items.map((qual: DisplayQualification) => {
                      const isSummaryRow = Boolean(qual.sourceIds && qual.sourceIds.length > 1);
                      const sourceFile = qual.file_id ? fileById.get(qual.file_id) : undefined;
                      return (
                        <TableRow key={qual.id} hover>
                          <TableCell padding="checkbox">
                            <Checkbox
                              checked={!isSummaryRow && selectedQualificationIds.has(qual.id)}
                              onChange={() => handleToggleQualification(qual.id)}
                              disabled={isSummaryRow}
                              size="small"
                              sx={{ color: '#7C4DFF', '&.Mui-checked': { color: '#7C4DFF' } }}
                            />
                          </TableCell>
                          {qualificationColumns.map((column) => {
                            if (column.key === 'issue_date') {
                              return (
                                <TableCell key={column.key} sx={{ color: '#666' }}>
                                  {qual.issue_date ? formatDate(qual.issue_date) : '—'}
                                </TableCell>
                              );
                            }
                            if (column.key === 'expiry_date') {
                              const expiryDisplay = getQualificationExpiryDisplay(
                                qual,
                                formatDate,
                              );
                              return (
                                <TableCell key={column.key}>
                                  <Typography
                                    variant="body2"
                                    sx={{ color: expiryDisplay.color, fontWeight: 500 }}
                                  >
                                    {expiryDisplay.text}
                                  </Typography>
                                </TableCell>
                              );
                            }
                            const value = getQualificationCellValue(qual, column.key);
                            return (
                              <TableCell
                                key={column.key}
                                sx={{
                                  color: column.key === 'name' ? '#333' : '#666',
                                  fontWeight: column.key === 'name' ? 500 : 400,
                                }}
                              >
                                {value || '—'}
                              </TableCell>
                            );
                          })}
                          <TableCell>
                            <IconButton
                              size="small"
                              onClick={() => sourceFile && setPreviewFile(sourceFile)}
                              disabled={isSummaryRow || !sourceFile}
                              sx={{ color: '#7C4DFF' }}
                              title={
                                isSummaryRow
                                  ? '汇总行请切换到明细后查看源文件'
                                  : sourceFile
                                    ? '查看源文件'
                                    : '未关联源文件'
                              }
                            >
                              <VisibilityIcon fontSize="small" />
                            </IconButton>
                            <IconButton
                              size="small"
                              onClick={() => handleEditClick(qual)}
                              disabled={isSummaryRow}
                              sx={{ color: '#7C4DFF' }}
                              title={isSummaryRow ? '汇总行不可直接编辑，请切换到明细' : '编辑'}
                            >
                              <EditIcon fontSize="small" />
                            </IconButton>
                            <IconButton
                              size="small"
                              onClick={() => setDeleteId(qual.id)}
                              disabled={isSummaryRow}
                              sx={{ color: '#EF5350' }}
                              title={isSummaryRow ? '汇总行不可直接删除，请切换到明细' : '删除'}
                            >
                              <DeleteIcon fontSize="small" />
                            </IconButton>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
            {displayedQualifications.length > 0 && (
              <PaginationFooter
                page={qualificationPagination.page}
                pageCount={qualificationPagination.pageCount}
                startIndex={qualificationPagination.startIndex}
                endIndex={qualificationPagination.endIndex}
                total={qualificationPagination.total}
                onPageChange={setQualificationPage}
              />
            )}
          </Paper>
        </Box>
      )}

      {/* ===== Tab 2: Performance projects ===== */}
      {activeTab === 2 && (
        <Box>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="body2" sx={{ color: '#666' }}>
              业绩项目独立管理，可关联已上传的“业绩”分类证明文件。
            </Typography>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Tooltip title="上传业绩证明文件" arrow>
                <span>
                  <Button
                    variant="outlined"
                    startIcon={<CloudUploadIcon />}
                    onClick={() => performanceUploadInputRef.current?.click()}
                    disabled={uploading}
                    sx={{
                      borderColor: '#7C4DFF',
                      color: '#7C4DFF',
                      '&:hover': { borderColor: '#651FFF', backgroundColor: '#F4EEFF' },
                    }}
                  >
                    {uploading ? '上传中...' : '上传文件'}
                  </Button>
                </span>
              </Tooltip>
              <input
                ref={performanceUploadInputRef}
                type="file"
                accept=".pdf,.docx,.doc,.xlsx,.xls,.jpg,.png"
                multiple
                style={{ display: 'none' }}
                onChange={handlePerformanceUploadChange}
              />
              <Button
                variant="contained"
                startIcon={<AddIcon />}
                onClick={handleAddPerformanceClick}
                sx={{
                  backgroundColor: '#7C4DFF',
                  '&:hover': { backgroundColor: '#651FFF' },
                }}
              >
                新增业绩项目
              </Button>
            </Box>
          </Box>

          {performanceFiles.length > 0 && (
            <Alert
              severity={unlinkedPerformanceFiles.length > 0 ? 'warning' : 'success'}
              sx={{ mb: 2 }}
            >
              已上传 {performanceFiles.length} 个业绩文件，
              {unlinkedPerformanceFiles.length > 0 ? (
                <>
                  其中 {unlinkedPerformanceFiles.length} 个尚未关联到业绩项目：
                  {unlinkedPerformanceFiles.slice(0, 5).map((file) => file.filename).join('、')}
                  {unlinkedPerformanceFiles.length > 5 ? ' 等' : ''}。
                </>
              ) : (
                <>已全部关联到业绩项目。</>
              )}
            </Alert>
          )}

          <Paper
            sx={{
              backgroundColor: '#FFFFFF',
              border: '1px solid #EDE7F6',
              borderRadius: 2,
              overflow: 'hidden',
            }}
          >
            {performanceProjects.length === 0 ? (
              <Typography
                variant="body2"
                sx={{ color: '#999', py: 4, textAlign: 'center' }}
              >
                暂无业绩项目，请手动新增项目并关联业绩证明文件
              </Typography>
            ) : (
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow sx={{ backgroundColor: '#F9F7FF' }}>
                      <TableCell sx={{ fontWeight: 600, color: '#666' }}>项目名称</TableCell>
                      <TableCell sx={{ fontWeight: 600, color: '#666' }}>甲方/客户</TableCell>
                      <TableCell sx={{ fontWeight: 600, color: '#666' }}>合同编号</TableCell>
                      <TableCell sx={{ fontWeight: 600, color: '#666' }}>合同金额</TableCell>
                      <TableCell sx={{ fontWeight: 600, color: '#666' }}>签订日期</TableCell>
                      <TableCell sx={{ fontWeight: 600, color: '#666' }}>完成/验收</TableCell>
                      <TableCell sx={{ fontWeight: 600, color: '#666' }}>年度</TableCell>
                      <TableCell sx={{ fontWeight: 600, color: '#666' }}>证明文件</TableCell>
                      <TableCell sx={{ fontWeight: 600, color: '#666' }}>操作</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {performanceProjectPagination.items.map((project) => (
                      <TableRow key={project.id} hover>
                        <TableCell sx={{ color: '#333', fontWeight: 500 }}>
                          {project.project_name}
                        </TableCell>
                        <TableCell sx={{ color: '#666' }}>
                          {project.client_name || '—'}
                        </TableCell>
                        <TableCell sx={{ color: '#666' }}>
                          {project.contract_no || '—'}
                        </TableCell>
                        <TableCell sx={{ color: '#666' }}>
                          {project.contract_amount || '—'}
                        </TableCell>
                        <TableCell sx={{ color: '#666' }}>
                          {project.sign_date || '—'}
                        </TableCell>
                        <TableCell sx={{ color: '#666' }}>
                          {project.completion_date || '—'}
                        </TableCell>
                        <TableCell sx={{ color: '#666' }}>{project.year || '—'}</TableCell>
                        <TableCell sx={{ color: '#666' }}>
                          {project.file_ids.length === 0 ? (
                            '—'
                          ) : (
                            <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                              {project.file_ids.map((fileId) => {
                                const linkedFile = fileById.get(fileId);
                                return (
                                  <Chip
                                    key={fileId}
                                    size="small"
                                    icon={<VisibilityIcon sx={{ fontSize: 14 }} />}
                                    label={linkedFile?.filename || `文件 ${fileId}`}
                                    onClick={linkedFile ? () => setPreviewFile(linkedFile) : undefined}
                                    sx={{
                                      maxWidth: 180,
                                      color: linkedFile ? '#7C4DFF' : '#999',
                                      backgroundColor: '#F4EEFF',
                                      cursor: linkedFile ? 'pointer' : 'default',
                                      '& .MuiChip-label': {
                                        overflow: 'hidden',
                                        textOverflow: 'ellipsis',
                                      },
                                    }}
                                  />
                                );
                              })}
                            </Box>
                          )}
                        </TableCell>
                        <TableCell>
                          <IconButton
                            size="small"
                            onClick={() => handleEditPerformanceClick(project)}
                            sx={{ color: '#7C4DFF' }}
                          >
                            <EditIcon fontSize="small" />
                          </IconButton>
                          <IconButton
                            size="small"
                            onClick={() => setPerformanceDeleteId(project.id)}
                            sx={{ color: '#EF5350' }}
                          >
                            <DeleteIcon fontSize="small" />
                          </IconButton>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
            {performanceProjects.length > 0 && (
              <PaginationFooter
                page={performanceProjectPagination.page}
                pageCount={performanceProjectPagination.pageCount}
                startIndex={performanceProjectPagination.startIndex}
                endIndex={performanceProjectPagination.endIndex}
                total={performanceProjectPagination.total}
                onPageChange={setPerformanceProjectPage}
              />
            )}
          </Paper>
        </Box>
      )}

      {/* ===== Unified knowledge file preview dialog ===== */}
      <Dialog
        open={Boolean(previewFile)}
        onClose={() => setPreviewFile(null)}
        maxWidth="lg"
        fullWidth
        PaperProps={{ sx: { height: '88vh' } }}
      >
        <DialogTitle
          sx={{
            color: '#333',
            fontWeight: 600,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 2,
          }}
        >
          <Box sx={{ minWidth: 0 }}>
            <Typography variant="h6" sx={{ fontWeight: 600 }} noWrap>
              {previewFile?.filename || '文件预览'}
            </Typography>
            {previewFile && (
              <Typography variant="caption" sx={{ color: '#777' }}>
                {CATEGORY_LABELS[previewFile.category] || previewFile.category} · {previewFile.file_type || getFileExtension(previewFile.filename)}
              </Typography>
            )}
          </Box>
          {previewFile && (
            <Box sx={{ display: 'flex', gap: 1, flexShrink: 0 }}>
              <Button
                size="small"
                startIcon={<OpenInNewIcon />}
                href={buildPreviewUrl(previewFile.id)}
                target="_blank"
                rel="noreferrer"
                sx={{ color: '#7C4DFF' }}
              >
                新窗口
              </Button>
              <Button
                size="small"
                startIcon={<DownloadIcon />}
                href={buildPreviewUrl(previewFile.id, 'attachment')}
                sx={{ color: '#7C4DFF' }}
              >
                下载
              </Button>
            </Box>
          )}
        </DialogTitle>
        <DialogContent dividers sx={{ p: 0, backgroundColor: '#F7F7FA' }}>
          {previewFile && getPreviewKind(previewFile) === 'pdf' && (
            <Box
              component="iframe"
              title={previewFile.filename}
              src={buildPreviewUrl(previewFile.id)}
              sx={{
                width: '100%',
                height: '100%',
                border: 0,
                backgroundColor: '#fff',
              }}
            />
          )}
          {previewFile && getPreviewKind(previewFile) === 'image' && (
            <Box
              sx={{
                width: '100%',
                minHeight: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                p: 2,
              }}
            >
              <Box
                component="img"
                src={buildPreviewUrl(previewFile.id)}
                alt={previewFile.filename}
                sx={{
                  maxWidth: '100%',
                  maxHeight: '78vh',
                  objectFit: 'contain',
                  boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
                  backgroundColor: '#fff',
                }}
              />
            </Box>
          )}
          {previewFile && getPreviewKind(previewFile) === 'unsupported' && (
            <Box
              sx={{
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 2,
                p: 4,
                textAlign: 'center',
              }}
            >
              <Typography variant="h6" sx={{ color: '#333', fontWeight: 600 }}>
                当前文件格式不支持网页内直接预览
              </Typography>
              <Typography variant="body2" sx={{ color: '#666', maxWidth: 520 }}>
                PDF 和图片可直接在页面查看；Word、Excel 等 Office 文件请先下载或在新窗口打开。
                后续如果需要，也可以加“上传后自动转 PDF 预览”。
              </Typography>
              <Box sx={{ display: 'flex', gap: 1 }}>
                <Button
                  variant="outlined"
                  startIcon={<OpenInNewIcon />}
                  href={buildPreviewUrl(previewFile.id)}
                  target="_blank"
                  rel="noreferrer"
                  sx={{ borderColor: '#7C4DFF', color: '#7C4DFF' }}
                >
                  新窗口打开
                </Button>
                <Button
                  variant="contained"
                  startIcon={<DownloadIcon />}
                  href={buildPreviewUrl(previewFile.id, 'attachment')}
                  sx={{ backgroundColor: '#7C4DFF', '&:hover': { backgroundColor: '#651FFF' } }}
                >
                  下载文件
                </Button>
              </Box>
            </Box>
          )}
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={() => setPreviewFile(null)} sx={{ color: '#666' }}>
            关闭
          </Button>
        </DialogActions>
      </Dialog>

      {/* ===== Qualification form dialog (add / edit) ===== */}
      <Dialog
        open={formOpen}
        onClose={() => setFormOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle sx={{ color: '#7C4DFF', fontWeight: 600 }}>
          {formMode === 'add' ? '新增资质' : '编辑资质'}
        </DialogTitle>
        <DialogContent>
          {formError && (
            <Alert severity="error" sx={{ mb: 2 }} onClose={() => setFormError(null)}>
              {formError}
            </Alert>
          )}
          <Grid container spacing={2} sx={{ mt: 0.5 }}>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="名称 *"
                value={formData.name}
                onChange={(e) => handleFieldChange('name', e.target.value)}
                size="small"
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="编号 *"
                value={formData.number}
                onChange={(e) => handleFieldChange('number', e.target.value)}
                size="small"
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="发证日期"
                type="date"
                value={formData.issue_date}
                onChange={(e) => handleFieldChange('issue_date', e.target.value)}
                size="small"
                InputLabelProps={{ shrink: true }}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="有效期至"
                type="date"
                value={formData.expiry_date}
                onChange={(e) => handleFieldChange('expiry_date', e.target.value)}
                size="small"
                InputLabelProps={{ shrink: true }}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="发证机构"
                value={formData.issuing_authority}
                onChange={(e) => handleFieldChange('issuing_authority', e.target.value)}
                size="small"
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="认证范围"
                value={formData.scope}
                onChange={(e) => handleFieldChange('scope', e.target.value)}
                size="small"
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="等级"
                value={formData.level}
                onChange={(e) => handleFieldChange('level', e.target.value)}
                size="small"
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="持证主体"
                value={formData.holder}
                onChange={(e) => handleFieldChange('holder', e.target.value)}
                size="small"
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <FormControl fullWidth size="small">
                <InputLabel>分类</InputLabel>
                <Select
                  value={formData.category}
                  label="分类"
                  onChange={(e) =>
                    handleFieldChange('category', e.target.value)
                  }
                >
                  {getQualificationCategoryOptions().map((opt) => (
                    <MenuItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button onClick={() => setFormOpen(false)} sx={{ color: '#666' }}>
            取消
          </Button>
          <Button
            variant="contained"
            onClick={handleFormSubmit}
            disabled={formSaving}
            sx={{
              backgroundColor: '#7C4DFF',
              '&:hover': { backgroundColor: '#651FFF' },
            }}
          >
            {formSaving ? <CircularProgress size={20} color="inherit" /> : '保存'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* ===== Performance project form dialog ===== */}
      <Dialog
        open={performanceFormOpen}
        onClose={() => setPerformanceFormOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle sx={{ color: '#7C4DFF', fontWeight: 600 }}>
          {performanceFormMode === 'add' ? '新增业绩项目' : '编辑业绩项目'}
        </DialogTitle>
        <DialogContent>
          {performanceFormError && (
            <Alert
              severity="error"
              sx={{ mb: 2 }}
              onClose={() => setPerformanceFormError(null)}
            >
              {performanceFormError}
            </Alert>
          )}
          <Grid container spacing={2} sx={{ mt: 0.5 }}>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="项目名称 *"
                value={performanceFormData.project_name}
                onChange={(e) => handlePerformanceFieldChange('project_name', e.target.value)}
                size="small"
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="甲方/客户"
                value={performanceFormData.client_name}
                onChange={(e) => handlePerformanceFieldChange('client_name', e.target.value)}
                size="small"
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="合同编号"
                value={performanceFormData.contract_no}
                onChange={(e) => handlePerformanceFieldChange('contract_no', e.target.value)}
                size="small"
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="合同金额"
                value={performanceFormData.contract_amount}
                onChange={(e) => handlePerformanceFieldChange('contract_amount', e.target.value)}
                size="small"
              />
            </Grid>
            <Grid item xs={12} sm={4}>
              <TextField
                fullWidth
                label="签订日期"
                type="date"
                value={performanceFormData.sign_date}
                onChange={(e) => handlePerformanceFieldChange('sign_date', e.target.value)}
                size="small"
                InputLabelProps={{ shrink: true }}
              />
            </Grid>
            <Grid item xs={12} sm={4}>
              <TextField
                fullWidth
                label="完成/验收日期"
                type="date"
                value={performanceFormData.completion_date}
                onChange={(e) => handlePerformanceFieldChange('completion_date', e.target.value)}
                size="small"
                InputLabelProps={{ shrink: true }}
              />
            </Grid>
            <Grid item xs={12} sm={4}>
              <TextField
                fullWidth
                label="所属年度"
                value={performanceFormData.year}
                onChange={(e) => handlePerformanceFieldChange('year', e.target.value)}
                size="small"
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="项目内容/供货范围"
                value={performanceFormData.project_scope}
                onChange={(e) => handlePerformanceFieldChange('project_scope', e.target.value)}
                size="small"
                multiline
                minRows={2}
              />
            </Grid>
            <Grid item xs={12}>
              <FormControl fullWidth size="small">
                <InputLabel>关联证明文件</InputLabel>
                <Select
                  multiple
                  value={performanceFormData.file_ids}
                  input={<OutlinedInput label="关联证明文件" />}
                  onChange={(e) =>
                    handlePerformanceFieldChange(
                      'file_ids',
                      typeof e.target.value === 'string'
                        ? []
                        : (e.target.value as number[]),
                    )
                  }
                  renderValue={(selected) =>
                    selected
                      .map((id) => performanceFiles.find((file) => file.id === id)?.filename || id)
                      .join('，')
                  }
                >
                  {performanceFiles.length === 0 ? (
                    <MenuItem disabled value="">
                      暂无业绩分类文件
                    </MenuItem>
                  ) : (
                    performanceFiles.map((file) => (
                      <MenuItem key={file.id} value={file.id}>
                        <Checkbox checked={performanceFormData.file_ids.includes(file.id)} />
                        {file.filename}
                      </MenuItem>
                    ))
                  )}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="备注"
                value={performanceFormData.remark}
                onChange={(e) => handlePerformanceFieldChange('remark', e.target.value)}
                size="small"
                multiline
                minRows={2}
              />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button onClick={() => setPerformanceFormOpen(false)} sx={{ color: '#666' }}>
            取消
          </Button>
          <Button
            variant="contained"
            onClick={handlePerformanceFormSubmit}
            disabled={performanceFormSaving}
            sx={{
              backgroundColor: '#7C4DFF',
              '&:hover': { backgroundColor: '#651FFF' },
            }}
          >
            {performanceFormSaving ? <CircularProgress size={20} color="inherit" /> : '保存'}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={performanceDeleteId !== null}
        onClose={() => setPerformanceDeleteId(null)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle sx={{ color: '#333', fontWeight: 600 }}>确认删除业绩项目</DialogTitle>
        <DialogContent>
          <Typography variant="body1" sx={{ color: '#666' }}>
            确定要删除该业绩项目吗？此操作不会删除已上传的证明文件。
          </Typography>
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button onClick={() => setPerformanceDeleteId(null)} sx={{ color: '#666' }}>
            取消
          </Button>
          <Button
            variant="contained"
            onClick={handlePerformanceDeleteConfirm}
            disabled={performanceDeleting}
            sx={{
              backgroundColor: '#EF5350',
              '&:hover': { backgroundColor: '#D32F2F' },
            }}
          >
            {performanceDeleting ? <CircularProgress size={20} color="inherit" /> : '删除'}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={performanceImportOpen}
        onClose={() => setPerformanceImportOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle sx={{ color: '#7C4DFF', fontWeight: 600 }}>
          批量导入年度总表
        </DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ color: '#666', mb: 1.5 }}>
            从 Excel/WPS 年度总表复制包含表头的多行内容后粘贴。必须包含“项目名称/项目/业绩名称”列。
          </Typography>
          <TextField
            fullWidth
            multiline
            minRows={8}
            placeholder={'项目名称\t甲方\t合同编号\t合同金额\t签订日期\t验收日期\t项目内容\t年度\n智慧园区项目\t某某公司\tHT-001\t120万元\t2024-01-02\t2024-10-01\t弱电智能化\t2024'}
            value={performanceImportText}
            onChange={(e) => setPerformanceImportText(e.target.value)}
            size="small"
          />
          {performanceImportText.trim() && (
            <Box sx={{ mt: 2 }}>
              {performanceImportResult.errors.length > 0 ? (
                <Alert severity="error">
                  {performanceImportResult.errors.join('；')}
                </Alert>
              ) : (
                <Alert severity="success">
                  已解析 {performanceImportResult.projects.length} 条业绩项目，
                  自动关联 {performanceImportMatchedFileCount} 个业绩文件。确认后将批量新增。
                </Alert>
              )}
              {performanceImportResult.projects.length > 0 && (
                <TableContainer sx={{ mt: 1.5, border: '1px solid #EDE7F6', borderRadius: 1 }}>
                  <Table size="small">
                    <TableHead>
                      <TableRow sx={{ backgroundColor: '#F9F7FF' }}>
                        <TableCell>项目名称</TableCell>
                        <TableCell>甲方/客户</TableCell>
                        <TableCell>合同金额</TableCell>
                        <TableCell>年度</TableCell>
                        <TableCell>自动关联文件</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {performanceImportResult.projects.slice(0, 5).map((project, index) => (
                        <TableRow key={`${project.project_name}-${index}`}>
                          <TableCell>{project.project_name}</TableCell>
                          <TableCell>{project.client_name || '—'}</TableCell>
                          <TableCell>{project.contract_amount || '—'}</TableCell>
                          <TableCell>{project.year || '—'}</TableCell>
                          <TableCell>{project.file_ids?.length || 0} 个</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button
            onClick={() => setPerformanceImportOpen(false)}
            disabled={performanceImporting}
            sx={{ color: '#666' }}
          >
            取消
          </Button>
          <Button
            variant="contained"
            onClick={handlePerformanceImportConfirm}
            disabled={
              performanceImporting ||
              performanceImportResult.projects.length === 0 ||
              performanceImportResult.errors.length > 0
            }
            sx={{
              backgroundColor: '#7C4DFF',
              '&:hover': { backgroundColor: '#651FFF' },
            }}
          >
            {performanceImporting ? <CircularProgress size={20} color="inherit" /> : '确认导入'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* ===== Delete confirmation dialog ===== */}
      <Dialog open={deleteId !== null} onClose={() => setDeleteId(null)} maxWidth="xs" fullWidth>
        <DialogTitle sx={{ color: '#333', fontWeight: 600 }}>确认删除</DialogTitle>
        <DialogContent>
          <Typography variant="body1" sx={{ color: '#666' }}>
            确定要删除该资质吗？此操作不可撤销。
          </Typography>
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button onClick={() => setDeleteId(null)} sx={{ color: '#666' }}>
            取消
          </Button>
          <Button
            variant="contained"
            onClick={handleDeleteConfirm}
            disabled={deleting}
            sx={{
              backgroundColor: '#EF5350',
              '&:hover': { backgroundColor: '#D32F2F' },
            }}
          >
            {deleting ? <CircularProgress size={20} color="inherit" /> : '删除'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* ===== Bulk category dialog ===== */}
      <Dialog
        open={bulkCategoryOpen}
        onClose={() => setBulkCategoryOpen(false)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle sx={{ color: '#333', fontWeight: 600 }}>批量修改分类</DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ color: '#666', mb: 2 }}>
            将选中的 {selectedQualificationIds.size} 条资质改为以下分类；有关联源文件的记录会同步修改源文件分类，避免重新解析后分类回退。
          </Typography>
          <FormControl fullWidth size="small">
            <InputLabel>目标分类</InputLabel>
            <Select
              value={bulkTargetCategory}
              label="目标分类"
              onChange={(e) =>
                setBulkTargetCategory(e.target.value as KnowledgeCategory | 'other')
              }
            >
              {getQualificationCategoryOptions().map((opt) => (
                <MenuItem key={opt.value} value={opt.value}>
                  {opt.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button
            onClick={() => setBulkCategoryOpen(false)}
            disabled={bulkUpdatingCategory}
            sx={{ color: '#666' }}
          >
            取消
          </Button>
          <Button
            variant="contained"
            onClick={handleBulkCategoryConfirm}
            disabled={bulkUpdatingCategory}
            sx={{
              backgroundColor: '#7C4DFF',
              '&:hover': { backgroundColor: '#651FFF' },
            }}
          >
            {bulkUpdatingCategory ? <CircularProgress size={20} color="inherit" /> : '确认修改'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* ===== Bulk delete confirmation dialog ===== */}
      <Dialog
        open={bulkDeleteOpen}
        onClose={() => setBulkDeleteOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle sx={{ color: '#333', fontWeight: 600 }}>确认批量删除</DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 2 }}>
            这是源文件级删除。有关联源文件的资质会删除整个源文件及该文件解析出的全部资质记录；无源文件的手动资质只删除记录。
          </Alert>
          <Typography variant="body2" sx={{ color: '#666' }}>
            当前选择 {bulkDeletePreview.selectedQualificationCount} 条资质，将删除：
          </Typography>
          <Box component="ul" sx={{ mt: 1, mb: 0, color: '#666', pl: 3 }}>
            <li>{bulkDeletePreview.sourceFileCount} 个源文件及其解析出的全部资质记录</li>
            <li>{bulkDeletePreview.manualQualificationCount} 条无源文件的手动资质记录</li>
          </Box>
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button
            onClick={() => setBulkDeleteOpen(false)}
            disabled={bulkDeleting}
            sx={{ color: '#666' }}
          >
            取消
          </Button>
          <Button
            variant="contained"
            onClick={handleBulkDeleteConfirm}
            disabled={bulkDeleting}
            sx={{
              backgroundColor: '#EF5350',
              '&:hover': { backgroundColor: '#D32F2F' },
            }}
          >
            {bulkDeleting ? <CircularProgress size={20} color="inherit" /> : '确认删除'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* ===== File delete confirmation dialog ===== */}
      <Dialog
        open={bulkFileDeleteOpen}
        onClose={() => setBulkFileDeleteOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle sx={{ color: '#333', fontWeight: 600 }}>确认批量删除文件</DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 2 }}>
            将删除选中的 {selectedFileIds.size} 个源文件、这些文件解析出的全部资质记录，以及本地物理文件。此操作不可撤销。
          </Alert>
          <Typography variant="body2" sx={{ color: '#666' }}>
            如果你已经在本地重新分好类，可以删除后按正确分类重新上传。
          </Typography>
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button
            onClick={() => setBulkFileDeleteOpen(false)}
            disabled={bulkFileDeleting}
            sx={{ color: '#666' }}
          >
            取消
          </Button>
          <Button
            variant="contained"
            onClick={handleBulkFileDeleteConfirm}
            disabled={bulkFileDeleting}
            sx={{
              backgroundColor: '#EF5350',
              '&:hover': { backgroundColor: '#D32F2F' },
            }}
          >
            {bulkFileDeleting ? <CircularProgress size={20} color="inherit" /> : '确认删除'}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={fileDeleteId !== null}
        onClose={() => setFileDeleteId(null)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle sx={{ color: '#333', fontWeight: 600 }}>确认删除文件</DialogTitle>
        <DialogContent>
          <Typography variant="body1" sx={{ color: '#666' }}>
            确定要删除该文件吗？同时会删除从该文件提取的所有资质记录。
          </Typography>
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button
            onClick={() => setFileDeleteId(null)}
            disabled={fileDeleting}
            sx={{ color: '#666' }}
          >
            取消
          </Button>
          <Button
            variant="contained"
            onClick={handleFileDeleteConfirm}
            disabled={fileDeleting}
            sx={{
              backgroundColor: '#EF5350',
              '&:hover': { backgroundColor: '#D32F2F' },
            }}
          >
            {fileDeleting ? <CircularProgress size={20} color="inherit" /> : '删除'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

const PaginationFooter: React.FC<{
  page: number;
  pageCount: number;
  startIndex: number;
  endIndex: number;
  total: number;
  onPageChange: (page: number) => void;
}> = ({
  page,
  pageCount,
  startIndex,
  endIndex,
  total,
  onPageChange,
}) => (
  <Box
    sx={{
      minHeight: 52,
      px: 2,
      borderTop: '1px solid #EDE7F6',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'flex-end',
      gap: 1.5,
      flexWrap: 'wrap',
    }}
  >
    <Typography variant="caption" sx={{ color: '#888' }}>
      {`${startIndex + 1}–${endIndex} / 共 ${total} 项`}
    </Typography>
    <Pagination
      count={pageCount}
      page={page}
      onChange={(_event, nextPage) => onPageChange(nextPage)}
      size="small"
      color="primary"
      shape="rounded"
      showFirstButton
      showLastButton
    />
  </Box>
);

export default KnowledgePage;
