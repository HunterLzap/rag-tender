import React, { useState } from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Box,
  Typography,
  Select,
  MenuItem,
  TextField,
  Chip,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Alert,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import ReportProblemOutlinedIcon from '@mui/icons-material/ReportProblemOutlined';
import type {
  ManualChecklistItemInput,
  SubmissionChecklist,
  SubmissionChecklistStatus,
} from '../types';
import {
  addManualChecklistItem,
  updateChecklistItem,
} from '../api/checklist';
import { isRedFlagChecklistItem } from './submissionChecklistRisk';

interface SubmissionChecklistTableProps {
  tenderId: number;
  items: SubmissionChecklist[];
  onUpdate: (updated: SubmissionChecklist) => void;
  onAdd: (newItem: SubmissionChecklist) => void;
}

const STATUS_CONFIG: Record<
  SubmissionChecklistStatus,
  { label: string; color: string; bg: string }
> = {
  not_started: { label: '未开始', color: '#666', bg: '#F0F0F0' },
  in_progress: { label: '进行中', color: '#E65100', bg: '#FFF3E0' },
  done: { label: '已完成', color: '#2E7D32', bg: '#E8F5E9' },
};

/**
 * Submission checklist table with three-tier status.
 *
 * Columns: 复选框 / 提交件名称 / 来源 / 状态下拉 / 备注
 * Status colors: not_started=gray / in_progress=orange / done=green
 *
 * Status changes save immediately. Supports manual item addition via dialog.
 */
const SubmissionChecklistTable: React.FC<SubmissionChecklistTableProps> = ({
  tenderId,
  items,
  onUpdate,
  onAdd,
}) => {
  const [remarkEdits, setRemarkEdits] = useState<Record<number, string>>({});
  const [savingRemarkId, setSavingRemarkId] = useState<number | null>(null);
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [newItem, setNewItem] = useState<ManualChecklistItemInput>({
    item_name: '',
    description: '',
    remark: '',
  });
  const [addError, setAddError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);

  const handleStatusChange = async (
    item: SubmissionChecklist,
    newStatus: SubmissionChecklistStatus,
  ) => {
    try {
      const updated = await updateChecklistItem(tenderId, item.id, {
        status: newStatus,
      });
      onUpdate(updated);
    } catch (err) {
      console.error('更新状态失败:', err);
    }
  };

  const handleRemarkSave = async (item: SubmissionChecklist) => {
    const newRemark = remarkEdits[item.id];
    if (newRemark === undefined) return;
    setSavingRemarkId(item.id);
    try {
      const updated = await updateChecklistItem(tenderId, item.id, {
        remark: newRemark || null,
      });
      onUpdate(updated);
      setRemarkEdits((prev) => {
        const next = { ...prev };
        delete next[item.id];
        return next;
      });
    } finally {
      setSavingRemarkId(null);
    }
  };

  const handleAddItem = async () => {
    if (!newItem.item_name.trim()) {
      setAddError('待办项名称不能为空');
      return;
    }
    setAdding(true);
    setAddError(null);
    try {
      const created = await addManualChecklistItem(tenderId, newItem);
      onAdd(created);
      setAddDialogOpen(false);
      setNewItem({ item_name: '', description: '', remark: '' });
    } catch (err) {
      setAddError(err instanceof Error ? err.message : '新增失败');
    } finally {
      setAdding(false);
    }
  };

  const completedCount = items.filter((i) => i.status === 'done').length;

  return (
    <Box>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          mb: 1.5,
        }}
      >
        <Typography variant="body2" sx={{ color: '#666' }}>
          共 {items.length} 项 · 已完成 {completedCount} 项
        </Typography>
        <Button
          size="small"
          startIcon={<AddIcon />}
          onClick={() => setAddDialogOpen(true)}
          sx={{
            color: '#7C4DFF',
            borderColor: '#7C4DFF',
          }}
        >
          手动新增待办
        </Button>
      </Box>

      <TableContainer
        component={Paper}
        sx={{
          backgroundColor: '#FFFFFF',
          boxShadow: 'none',
          border: '1px solid #EDE7F6',
        }}
      >
        <Table size="small">
          <TableHead>
            <TableRow sx={{ backgroundColor: '#F9F7FF' }}>
              <TableCell sx={{ fontWeight: 600, color: '#666', width: '35%' }}>
                提交件名称
              </TableCell>
              <TableCell sx={{ fontWeight: 600, color: '#666', width: '10%' }}>
                来源
              </TableCell>
              <TableCell sx={{ fontWeight: 600, color: '#666', width: '15%' }}>
                状态
              </TableCell>
              <TableCell sx={{ fontWeight: 600, color: '#666', width: '30%' }}>
                备注
              </TableCell>
              <TableCell sx={{ fontWeight: 600, color: '#666', width: '10%' }}>
                操作
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {items.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} align="center" sx={{ py: 4 }}>
                  <Typography variant="body2" sx={{ color: '#999' }}>
                    暂无待办项
                  </Typography>
                </TableCell>
              </TableRow>
            )}
            {items.map((item) => {
              const remarkEdit = remarkEdits[item.id];
              const hasRemarkEdit = item.id in remarkEdits;
              const isRedFlag = isRedFlagChecklistItem(item);

              return (
                <TableRow
                  key={item.id}
                  sx={{
                    '&:hover': { backgroundColor: '#F9F7FF' },
                  }}
                >
                  <TableCell>
                    <Box
                      sx={{ color: '#333', fontWeight: 500 }}
                    >
                      <Typography
                        variant="body2"
                        component="span"
                        sx={{ color: '#333', fontWeight: 500 }}
                      >
                        {item.item_name}
                      </Typography>
                      {isRedFlag && (
                        <Chip
                          icon={<ReportProblemOutlinedIcon />}
                          label="红线"
                          size="small"
                          sx={{
                            ml: 1,
                            height: 20,
                            fontSize: 10,
                            backgroundColor: '#FFEBEE',
                            color: '#C62828',
                            '& .MuiChip-icon': {
                              color: '#C62828',
                              fontSize: 14,
                            },
                          }}
                        />
                      )}
                    </Box>
                    {item.description && (
                      <Typography
                        variant="caption"
                        sx={{ color: '#999', display: 'block' }}
                      >
                        {item.description}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={item.requirement_id ? '标书提取' : '手动新增'}
                      size="small"
                      sx={{
                        height: 20,
                        fontSize: 10,
                        backgroundColor: item.requirement_id
                          ? '#EDE7F6'
                          : '#E0F7FA',
                        color: item.requirement_id ? '#7C4DFF' : '#00838F',
                      }}
                    />
                  </TableCell>
                  <TableCell>
                    <Select
                      size="small"
                      value={item.status}
                      onChange={(e) =>
                        handleStatusChange(
                          item,
                          e.target.value as SubmissionChecklistStatus,
                        )
                      }
                      sx={{
                        width: '100%',
                        fontSize: 12,
                        '& .MuiOutlinedInput-root': { borderRadius: 0 },
                      }}
                      renderValue={(value) => {
                        const config = STATUS_CONFIG[value];
                        return (
                          <Chip
                            label={config.label}
                            size="small"
                            sx={{
                              height: 20,
                              fontSize: 10,
                              backgroundColor: config.bg,
                              color: config.color,
                            }}
                          />
                        );
                      }}
                    >
                      {(
                        Object.keys(STATUS_CONFIG) as SubmissionChecklistStatus[]
                      ).map((status) => (
                        <MenuItem key={status} value={status}>
                          {STATUS_CONFIG[status].label}
                        </MenuItem>
                      ))}
                    </Select>
                  </TableCell>
                  <TableCell>
                    <TextField
                      size="small"
                      fullWidth
                      value={
                        hasRemarkEdit ? remarkEdit : item.remark || ''
                      }
                      onChange={(e) =>
                        setRemarkEdits((prev) => ({
                          ...prev,
                          [item.id]: e.target.value,
                        }))
                      }
                      placeholder="备注"
                      sx={{ '& .MuiOutlinedInput-root': { borderRadius: 0 } }}
                    />
                  </TableCell>
                  <TableCell>
                    <Button
                      size="small"
                      disabled={
                        !hasRemarkEdit || savingRemarkId === item.id
                      }
                      onClick={() => handleRemarkSave(item)}
                      sx={{
                        color: hasRemarkEdit ? '#7C4DFF' : '#CCC',
                        fontSize: 12,
                        minWidth: 'auto',
                      }}
                    >
                      保存
                    </Button>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Manual add dialog */}
      <Dialog
        open={addDialogOpen}
        onClose={() => setAddDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle sx={{ color: '#7C4DFF', fontWeight: 600 }}>
          新增待办项
        </DialogTitle>
        <DialogContent>
          {addError && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {addError}
            </Alert>
          )}
          <TextField
            autoFocus
            size="small"
            fullWidth
            label="待办项名称"
            value={newItem.item_name}
            onChange={(e) =>
              setNewItem((prev) => ({ ...prev, item_name: e.target.value }))
            }
            sx={{ mt: 1, mb: 2, '& .MuiOutlinedInput-root': { borderRadius: 0 } }}
          />
          <TextField
            size="small"
            fullWidth
            multiline
            minRows={2}
            label="详细说明"
            value={newItem.description || ''}
            onChange={(e) =>
              setNewItem((prev) => ({
                ...prev,
                description: e.target.value || null,
              }))
            }
            sx={{ mb: 2, '& .MuiOutlinedInput-root': { borderRadius: 0 } }}
          />
          <TextField
            size="small"
            fullWidth
            label="备注"
            value={newItem.remark || ''}
            onChange={(e) =>
              setNewItem((prev) => ({
                ...prev,
                remark: e.target.value || null,
              }))
            }
            sx={{ '& .MuiOutlinedInput-root': { borderRadius: 0 } }}
          />
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button onClick={() => setAddDialogOpen(false)} sx={{ color: '#666' }}>
            取消
          </Button>
          <Button
            variant="contained"
            onClick={handleAddItem}
            disabled={adding}
            sx={{
              backgroundColor: '#7C4DFF',
              '&:hover': { backgroundColor: '#651FFF' },
            }}
          >
            {adding ? '添加中…' : '添加'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default SubmissionChecklistTable;
