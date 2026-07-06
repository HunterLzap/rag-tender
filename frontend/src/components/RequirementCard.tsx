import React, { useState } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Chip,
  Box,
  Collapse,
  IconButton,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import DescriptionIcon from '@mui/icons-material/Description';
import type { TenderRequirement, RequirementCategory, RequirementNature } from '../types';

interface RequirementCardProps {
  requirement: TenderRequirement;
  onViewSource?: (requirement: TenderRequirement) => void;
}

const CATEGORY_LABELS: Record<RequirementCategory, string> = {
  qualification: '资质',
  performance: '业绩',
  financial: '财务',
  personnel: '人员',
  other: '其他',
  product_spec: '产品参数',
  submission: '提交件',
};

const CATEGORY_COLORS: Record<RequirementCategory, string> = {
  qualification: '#7C4DFF',
  performance: '#5C6BC0',
  financial: '#26A69A',
  personnel: '#FF9800',
  other: '#78909C',
  product_spec: '#7C4DFF',
  submission: '#9C27B0',
};

const NATURE_STYLES: Record<RequirementNature, { label: string; bg: string; color: string }> = {
  capability: { label: '能力', bg: '#F0F0F0', color: '#666' },
  submission: { label: '提交', bg: '#FFF3E0', color: '#E65100' },
};

/**
 * Displays a single tender requirement with category tag, title, content,
 * and a "view source" action to jump to the original text.
 */
const RequirementCard: React.FC<RequirementCardProps> = ({ requirement, onViewSource }) => {
  const [expanded, setExpanded] = useState(false);

  const categoryLabel = CATEGORY_LABELS[requirement.category] || requirement.category;
  const categoryColor = CATEGORY_COLORS[requirement.category] || '#78909C';
  const natureStyle = NATURE_STYLES[requirement.requirement_nature] || NATURE_STYLES.capability;
  const isGrayZone = (requirement.content || '').includes('【灰色地带】');

  return (
    <Card
      sx={{
        mb: 1.5,
        backgroundColor: '#F9F7FF',
        border: '1px solid #EDE7F6',
        '&:hover': { boxShadow: '0 2px 8px rgba(124, 77, 255, 0.1)' },
      }}
    >
      <CardContent sx={{ py: 2, '&:last-child': { pb: 2 } }}>
        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
          {/* Checkbox-style indicator */}
          <Box
            sx={{
              width: 20,
              height: 20,
              borderRadius: '4px',
              border: `2px solid ${categoryColor}`,
              flexShrink: 0,
              mt: 0.3,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Typography sx={{ fontSize: 12, color: categoryColor }}>✓</Typography>
          </Box>

          <Box sx={{ flexGrow: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5, flexWrap: 'wrap' }}>
              <Chip
                label={categoryLabel}
                size="small"
                sx={{
                  height: 22,
                  fontSize: 11,
                  backgroundColor: '#EDE7F6',
                  color: categoryColor,
                  fontWeight: 600,
                }}
              />
              <Chip
                label={natureStyle.label}
                size="small"
                sx={{
                  height: 18,
                  fontSize: 10,
                  backgroundColor: natureStyle.bg,
                  color: natureStyle.color,
                }}
              />
              {requirement.is_hard && (
                <Chip
                  label="硬性"
                  size="small"
                  sx={{
                    height: 22,
                    fontSize: 11,
                    backgroundColor: '#FFEBEE',
                    color: '#EF5350',
                    fontWeight: 600,
                  }}
                />
              )}
              <Typography variant="body2" sx={{ fontWeight: 500, color: '#333' }}>
                {requirement.title || requirement.content}
              </Typography>
            </Box>

            {/* Gray zone warning */}
            {isGrayZone && (
              <Box
                sx={{
                  mb: 0.5,
                  px: 1,
                  py: 0.25,
                  backgroundColor: '#FFF3E0',
                  borderLeft: '3px solid #FF9800',
                  borderRadius: 0.5,
                }}
              >
                <Typography variant="caption" sx={{ color: '#E65100', fontSize: 11 }}>
                  ⚠ 灰色地带：请人工确认分类是否正确
                </Typography>
              </Box>
            )}

            {/* Numeric rule display */}
            {requirement.numeric_value && requirement.numeric_operator && (
              <Typography variant="caption" sx={{ color: '#7C4DFF', display: 'block', mb: 0.5 }}>
                数值要求：{requirement.numeric_operator} {requirement.numeric_value}
                {requirement.numeric_unit ? ` ${requirement.numeric_unit}` : ''}
              </Typography>
            )}

            {/* Expandable content */}
            {requirement.content && requirement.content !== requirement.title && (
              <>
                <IconButton
                  size="small"
                  onClick={() => setExpanded(!expanded)}
                  sx={{ p: 0, color: '#7C4DFF' }}
                >
                  <ExpandMoreIcon
                    sx={{
                      transform: expanded ? 'rotate(180deg)' : 'none',
                      transition: 'transform 0.2s',
                    }}
                  />
                </IconButton>
                <Collapse in={expanded} timeout="auto" unmountOnExit>
                  <Typography
                    variant="body2"
                    sx={{ color: '#666', mt: 1, whiteSpace: 'pre-wrap' }}
                  >
                    {requirement.content}
                  </Typography>
                </Collapse>
              </>
            )}

            {/* View source button */}
            <Box sx={{ mt: 0.5 }}>
              <IconButton
                size="small"
                onClick={() => onViewSource?.(requirement)}
                sx={{ color: '#7C4DFF', p: 0 }}
              >
                <DescriptionIcon sx={{ fontSize: 16, mr: 0.5 }} />
                <Typography variant="caption" sx={{ color: '#7C4DFF' }}>
                  查看原文{requirement.page_number ? ` (P${requirement.page_number})` : ''}
                </Typography>
              </IconButton>
            </Box>
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
};

export default RequirementCard;
