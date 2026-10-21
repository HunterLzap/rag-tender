import { Box, Stack, Typography } from '@mui/material';
import type { PageItem, SourceSpan } from '../lib/api';

interface Props {
  page: PageItem;
  highlight?: SourceSpan | null;
}

export default function PageViewer({ page, highlight }: Props) {
  const [x0, y0, x1, y1] = highlight?.bbox_json ?? [];
  const hasBox = highlight && highlight.page_id === page.id;
  return (
    <Stack spacing={1}>
      <Typography variant="caption" color="text.secondary">
        第 {page.page_index + 1} 页 · {page.parse_mode === 'text' ? '文本层' : '需要视觉识别'}
      </Typography>
      <Box className="page-canvas paper-frame">
        <img src={`/api/v2/pages/${page.id}/image`} alt={`第 ${page.page_index + 1} 页`} />
        {hasBox && (
          <Box
            sx={{
              position: 'absolute',
              left: `${(x0 / page.width) * 100}%`,
              top: `${(y0 / page.height) * 100}%`,
              width: `${((x1 - x0) / page.width) * 100}%`,
              height: `${((y1 - y0) / page.height) * 100}%`,
              border: '3px solid #B7432B',
              bgcolor: 'rgba(183, 67, 43, 0.12)',
              pointerEvents: 'none',
            }}
          />
        )}
      </Box>
    </Stack>
  );
}
