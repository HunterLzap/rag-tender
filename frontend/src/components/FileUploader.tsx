import React, { useState, useCallback, useEffect, useRef } from 'react';
import {
  Box,
  Typography,
  LinearProgress,
  IconButton,
  Chip,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  List,
  ListItem,
} from '@mui/material';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import DeleteIcon from '@mui/icons-material/Delete';
import InsertDriveFileIcon from '@mui/icons-material/InsertDriveFile';
import { shouldClearSelectedFiles } from './fileUploaderClearSignal';
import {
  getDefaultFileUploadCategoryOptions,
  type FileUploadCategoryOption,
} from './fileUploaderCategories';

interface FileUploaderProps {
  /** Accept attribute for file input */
  accept?: string;
  /** Show category selector */
  showCategory?: boolean;
  /** Allow multiple files */
  multiple?: boolean;
  /** Callback when files are selected */
  onFilesSelected: (files: File[], category?: string) => void;
  /** Upload progress (0-100) */
  progress?: number;
  /** Whether upload is in progress */
  uploading?: boolean;
  /** Max file size in MB */
  maxSizeMB?: number;
  /** Increment this key to clear selected files after external processing completes */
  clearKey?: number;
  /** Category options shown when showCategory is true */
  categoryOptions?: FileUploadCategoryOption[];
  /** Fixed category used when category selector is hidden */
  fixedCategory?: string;
}

/**
 * Drag-and-drop file uploader with optional category selector.
 * Supports multiple files, progress display, and file list preview.
 */
const FileUploader: React.FC<FileUploaderProps> = ({
  accept = '*',
  showCategory = false,
  multiple = true,
  onFilesSelected,
  progress,
  uploading = false,
  maxSizeMB = 100,
  clearKey,
  categoryOptions = getDefaultFileUploadCategoryOptions(),
  fixedCategory,
}) => {
  const [dragOver, setDragOver] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [category, setCategory] = useState('enterprise');
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const previousClearKeyRef = useRef<number | undefined>(clearKey);

  useEffect(() => {
    if (shouldClearSelectedFiles(previousClearKeyRef.current, clearKey)) {
      setSelectedFiles([]);
      setError(null);
      if (inputRef.current) {
        inputRef.current.value = '';
      }
    }
    previousClearKeyRef.current = clearKey;
  }, [clearKey]);

  const validateFiles = useCallback(
    (files: File[]): File[] => {
      const valid: File[] = [];
      const maxBytes = maxSizeMB * 1024 * 1024;
      for (const file of files) {
        if (file.size > maxBytes) {
          setError(`文件 "${file.name}" 超过 ${maxSizeMB}MB 限制`);
          continue;
        }
        valid.push(file);
      }
      return valid;
    },
    [maxSizeMB]
  );

  const handleFiles = useCallback(
    (fileList: FileList | null) => {
      if (!fileList || fileList.length === 0) return;
      setError(null);
      const files = Array.from(fileList);
      const valid = validateFiles(files);
      const newFiles = multiple ? [...selectedFiles, ...valid] : valid;
      setSelectedFiles(newFiles);
      onFilesSelected(newFiles, showCategory ? category : fixedCategory);
    },
    [selectedFiles, multiple, validateFiles, onFilesSelected, showCategory, category, fixedCategory]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setDragOver(false);
      handleFiles(e.dataTransfer.files);
    },
    [handleFiles]
  );

  const handleDragOver = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
  }, []);

  const handleClick = useCallback(() => {
    inputRef.current?.click();
  }, []);

  const handleRemove = useCallback(
    (index: number) => {
      const newFiles = selectedFiles.filter((_, i) => i !== index);
      setSelectedFiles(newFiles);
      onFilesSelected(newFiles, showCategory ? category : fixedCategory);
    },
    [selectedFiles, onFilesSelected, showCategory, category, fixedCategory]
  );

  const formatSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <Box>
      {showCategory && (
        <FormControl fullWidth size="small" sx={{ mb: 2 }}>
          <InputLabel>文件分类</InputLabel>
          <Select
            value={category}
            label="文件分类"
            onChange={(e) => setCategory(e.target.value)}
          >
            {categoryOptions.map((c) => (
              <MenuItem key={c.value} value={c.value}>
                {c.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      )}

      {/* Drop zone */}
      <Box
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={handleClick}
        sx={{
          border: `2px dashed ${dragOver ? '#7C4DFF' : '#D1C4E9'}`,
          borderRadius: 3,
          p: 4,
          textAlign: 'center',
          cursor: 'pointer',
          backgroundColor: dragOver ? '#EDE7F6' : '#F9F7FF',
          transition: 'all 0.2s ease',
          '&:hover': {
            borderColor: '#7C4DFF',
            backgroundColor: '#EDE7F6',
          },
        }}
      >
        <CloudUploadIcon sx={{ fontSize: 48, color: '#7C4DFF', mb: 1 }} />
        <Typography variant="body1" sx={{ color: '#333', fontWeight: 500, mb: 0.5 }}>
          拖拽文件到此处或点击上传
        </Typography>
        <Typography variant="caption" sx={{ color: '#999' }}>
          支持 {accept === '*' ? '所有格式' : accept} · 最大 {maxSizeMB}MB
        </Typography>
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          multiple={multiple}
          style={{ display: 'none' }}
          onChange={(e) => handleFiles(e.target.files)}
        />
      </Box>

      {/* Error message */}
      {error && (
        <Typography variant="body2" sx={{ color: '#EF5350', mt: 1 }}>
          {error}
        </Typography>
      )}

      {/* Progress bar */}
      {uploading && typeof progress === 'number' && (
        <Box sx={{ mt: 2 }}>
          <LinearProgress
            variant="determinate"
            value={progress}
            sx={{
              height: 8,
              borderRadius: 4,
              backgroundColor: '#EDE7F6',
              '& .MuiLinearProgress-bar': { backgroundColor: '#7C4DFF' },
            }}
          />
          <Typography variant="caption" sx={{ color: '#666', mt: 0.5, display: 'block' }}>
            上传中... {progress}%
          </Typography>
        </Box>
      )}

      {/* Selected files list */}
      {selectedFiles.length > 0 && (
        <List sx={{ mt: 1 }}>
          {selectedFiles.map((file, index) => (
            <ListItem
              key={index}
              sx={{
                backgroundColor: '#F9F7FF',
                borderRadius: 2,
                mb: 0.5,
                pr: 1,
              }}
              secondaryAction={
                <IconButton edge="end" size="small" onClick={() => handleRemove(index)}>
                  <DeleteIcon sx={{ color: '#EF5350' }} />
                </IconButton>
              }
            >
              <InsertDriveFileIcon sx={{ color: '#7C4DFF', mr: 1.5 }} />
              <Box sx={{ flexGrow: 1 }}>
                <Typography variant="body2" sx={{ fontWeight: 500, color: '#333' }}>
                  {file.name}
                </Typography>
                <Chip
                  label={formatSize(file.size)}
                  size="small"
                  sx={{
                    height: 18,
                    fontSize: 11,
                    backgroundColor: '#EDE7F6',
                    color: '#7C4DFF',
                  }}
                />
              </Box>
            </ListItem>
          ))}
        </List>
      )}
    </Box>
  );
};

export default FileUploader;
