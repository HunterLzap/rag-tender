import React from 'react';
import { Chip } from '@mui/material';
import type { TenderStatus } from '../types';

interface StatusBadgeProps {
  status: TenderStatus;
}

const STATUS_CONFIG: Record<TenderStatus, { label: string; bg: string; color: string }> = {
  pending: { label: '待处理', bg: '#F5F5F5', color: '#999' },
  converting: { label: '转换中', bg: '#E3F2FD', color: '#1976D2' },
  parsing: { label: '解析中', bg: '#E3F2FD', color: '#1976D2' },
  extracting: { label: '提取中', bg: '#E3F2FD', color: '#1976D2' },
  retrying_vlm: { label: 'VLM兜底', bg: '#FFF3E0', color: '#E65100' },
  completed: { label: '已完成', bg: '#E8F5E9', color: '#4CAF50' },
  failed: { label: '失败', bg: '#FFEBEE', color: '#EF5350' },
};

/**
 * Status badge for tender parsing status.
 * pending=gray / parsing=blue / parsed=green / failed=red
 */
const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.pending;

  return (
    <Chip
      label={config.label}
      size="small"
      sx={{
        height: 22,
        fontSize: 11,
        fontWeight: 600,
        backgroundColor: config.bg,
        color: config.color,
      }}
    />
  );
};

export default StatusBadge;
