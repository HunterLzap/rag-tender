import React, { useState } from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Typography,
  Select,
  MenuItem,
  TextField,
  Chip,
  IconButton,
  Tooltip,
} from '@mui/material';
import SaveIcon from '@mui/icons-material/Save';
import type {
  TechnicalResponse,
  TechnicalResponseStatus,
} from '../types';
import { updateTechnicalResponse } from '../api/technical';

interface TechnicalResponseTableProps {
  tenderId: number;
  responses: TechnicalResponse[];
  onUpdate: (updated: TechnicalResponse) => void;
}

const STATUS_CONFIG: Record<
  TechnicalResponseStatus,
  { label: string; color: string; bg: string }
> = {
  pending: { label: '待响应', color: '#666', bg: '#F0F0F0' },
  met: { label: '满足', color: '#2E7D32', bg: '#E8F5E9' },
  deviated: { label: '偏离', color: '#C62828', bg: '#FFEBEE' },
  superior: { label: '优于', color: '#00838F', bg: '#E0F7FA' },
};

/**
 * Technical response comparison table.
 *
 * Columns: 参数要求 / 响应状态下拉 / 实际值输入框 / 备注
 * Status colors: pending=gray / met=green / deviated=red / superior=cyan
 *
 * Users manually fill in actual_value and set response_status.
 * Changes are saved via PUT API call.
 */
const TechnicalResponseTable: React.FC<TechnicalResponseTableProps> = ({
  tenderId,
  responses,
  onUpdate,
}) => {
  // Track local edits: { [responseId]: { actual_value, response_status, remark } }
  const [edits, setEdits] = useState<
    Record<
      number,
      { actual_value: string; response_status: TechnicalResponseStatus; remark: string }
    >
  >({});
  const [savingId, setSavingId] = useState<number | null>(null);

  const getEdit = (resp: TechnicalResponse) => {
    const edit = edits[resp.id];
    if (edit) return edit;
    return {
      actual_value: resp.actual_value || '',
      response_status: resp.response_status,
      remark: resp.remark || '',
    };
  };

  const setEdit = (
    respId: number,
    field: 'actual_value' | 'response_status' | 'remark',
    value: string,
  ) => {
    setEdits((prev) => {
      const existing = prev[respId] ?? {
        actual_value:
          responses.find((r) => r.id === respId)?.actual_value || '',
        response_status:
          responses.find((r) => r.id === respId)?.response_status ||
          'pending',
        remark: responses.find((r) => r.id === respId)?.remark || '',
      };
      return { ...prev, [respId]: { ...existing, [field]: value } };
    });
  };

  const handleSave = async (resp: TechnicalResponse) => {
    const edit = edits[resp.id];
    if (!edit) return;
    setSavingId(resp.id);
    try {
      const updated = await updateTechnicalResponse(tenderId, resp.id, {
        actual_value: edit.actual_value || null,
        response_status: edit.response_status,
        remark: edit.remark || null,
      });
      onUpdate(updated);
      setEdits((prev) => {
        const next = { ...prev };
        delete next[resp.id];
        return next;
      });
    } finally {
      setSavingId(null);
    }
  };

  const hasEdit = (respId: number) => respId in edits;

  return (
    <TableContainer
      component={Paper}
      sx={{ backgroundColor: '#FFFFFF', boxShadow: 'none', border: '1px solid #EDE7F6' }}
    >
      <Table size="small">
        <TableHead>
          <TableRow sx={{ backgroundColor: '#F9F7FF' }}>
            <TableCell sx={{ fontWeight: 600, color: '#666', width: '30%' }}>
              参数要求
            </TableCell>
            <TableCell sx={{ fontWeight: 600, color: '#666', width: '12%' }}>
              响应状态
            </TableCell>
            <TableCell sx={{ fontWeight: 600, color: '#666', width: '28%' }}>
              实际值
            </TableCell>
            <TableCell sx={{ fontWeight: 600, color: '#666', width: '22%' }}>
              备注
            </TableCell>
            <TableCell sx={{ fontWeight: 600, color: '#666', width: '8%' }}>
              操作
            </TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {responses.length === 0 && (
            <TableRow>
              <TableCell colSpan={5} align="center" sx={{ py: 4 }}>
                <Typography variant="body2" sx={{ color: '#999' }}>
                  暂无产品技术参数要求
                </Typography>
              </TableCell>
            </TableRow>
          )}
          {responses.map((resp) => {
            const edit = getEdit(resp);
            const isModified = hasEdit(resp.id);

            return (
              <TableRow
                key={resp.id}
                sx={{
                  backgroundColor: isModified ? '#FFFDE7' : 'inherit',
                  '&:hover': { backgroundColor: isModified ? '#FFF9C4' : '#F9F7FF' },
                }}
              >
                <TableCell>
                  <Typography variant="body2" sx={{ color: '#333', fontWeight: 500 }}>
                    {resp.spec_name || '—'}
                  </Typography>
                  {resp.required_value && (
                    <Typography variant="caption" sx={{ color: '#7C4DFF', display: 'block' }}>
                      要求：{resp.required_value}
                    </Typography>
                  )}
                  {resp.is_hard && (
                    <Chip
                      label="硬性"
                      size="small"
                      sx={{
                        height: 18,
                        fontSize: 10,
                        mt: 0.5,
                        backgroundColor: '#FFCDD2',
                        color: '#C62828',
                      }}
                    />
                  )}
                </TableCell>
                <TableCell>
                  <Select
                    size="small"
                    value={edit.response_status}
                    onChange={(e) =>
                      setEdit(resp.id, 'response_status', e.target.value)
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
                    {(Object.keys(STATUS_CONFIG) as TechnicalResponseStatus[]).map(
                      (status) => (
                        <MenuItem key={status} value={status}>
                          {STATUS_CONFIG[status].label}
                        </MenuItem>
                      ),
                    )}
                  </Select>
                </TableCell>
                <TableCell>
                  <TextField
                    size="small"
                    fullWidth
                    value={edit.actual_value}
                    onChange={(e) =>
                      setEdit(resp.id, 'actual_value', e.target.value)
                    }
                    placeholder="填写实际值"
                    sx={{ '& .MuiOutlinedInput-root': { borderRadius: 0 } }}
                  />
                </TableCell>
                <TableCell>
                  <TextField
                    size="small"
                    fullWidth
                    value={edit.remark}
                    onChange={(e) =>
                      setEdit(resp.id, 'remark', e.target.value)
                    }
                    placeholder="备注"
                    sx={{ '& .MuiOutlinedInput-root': { borderRadius: 0 } }}
                  />
                </TableCell>
                <TableCell>
                  <Tooltip title="保存">
                    <span>
                      <IconButton
                        size="small"
                        disabled={!isModified || savingId === resp.id}
                        onClick={() => handleSave(resp)}
                        sx={{ color: isModified ? '#7C4DFF' : '#CCC' }}
                      >
                        <SaveIcon sx={{ fontSize: 18 }} />
                      </IconButton>
                    </span>
                  </Tooltip>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </TableContainer>
  );
};

export default TechnicalResponseTable;
