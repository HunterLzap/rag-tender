import { useState, type PointerEvent } from 'react';
import { Alert, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, MenuItem, Stack, TextField, Typography } from '@mui/material';
import { useMutation } from '@tanstack/react-query';
import { api, apiError, type FillPlan, type FillTarget, type PageItem } from '../lib/api';

export default function FillTargetEditor({ plan, pages, target, onClose, onSaved }: {
  plan: FillPlan; pages: PageItem[]; target: FillTarget | null;
  onClose: () => void; onSaved: (plan: FillPlan, label: string) => Promise<void>;
}) {
  const [pageId, setPageId] = useState(target?.page_id ?? pages[0]?.id ?? '');
  const [label, setLabel] = useState(target?.label ?? '');
  const [kind, setKind] = useState(target?.kind ?? 'text_box');
  const [bbox, setBbox] = useState<number[] | null>(target?.bbox_json ?? null);
  const [anchor, setAnchor] = useState<number[] | null>(null);
  const page = pages.find((item) => item.id === pageId);
  const save = useMutation({
    mutationFn: async () => target
      ? (await api.patch<FillPlan>(`/fill-targets/${target.id}`, { label: label.trim(), ...(bbox?.some((value, index) => value !== target.bbox_json[index]) ? { bbox } : {}) })).data
      : (await api.post<FillPlan>(`/fill-plans/${plan.id}/targets`, { label: label.trim(), page_id: pageId, kind, bbox })).data,
    onSuccess: async (result) => { await onSaved(result, label.trim()); onClose(); },
  });
  function point(event: PointerEvent<SVGSVGElement>) {
    const bounds = event.currentTarget.getBoundingClientRect();
    return [
      Math.max(0, Math.min(page!.width, (event.clientX - bounds.left) / bounds.width * page!.width)),
      Math.max(0, Math.min(page!.height, (event.clientY - bounds.top) / bounds.height * page!.height)),
    ];
  }
  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="md">
      <DialogTitle>{target ? '修正填写位置' : '手工添加填写位置'}</DialogTitle>
      <DialogContent>
        <Stack spacing={2.25} sx={{ pt: 1 }}>
          <Alert severity="info">在原页中拖动框出实际可填写区域，再填写字段名称。保存后可输入建议内容并生成原页标注图，不调用模型。</Alert>
          {save.isError && <Alert severity="error">{apiError(save.error, '保存填写位置失败')}</Alert>}
          <Stack direction={{ xs: 'column', sm: 'row' }} gap={2}>
            <TextField required label="字段名称" value={label} onChange={(event) => setLabel(event.target.value)} placeholder="例如：投标人名称" />
            <TextField select label="模板页码" value={pageId} disabled={Boolean(target)} onChange={(event) => { setPageId(event.target.value); setBbox(null); }} sx={{ minWidth: 140 }}>
              {pages.map((item) => <MenuItem key={item.id} value={item.id}>第 {item.page_index + 1} 页</MenuItem>)}
            </TextField>
            {!target && <TextField select label="填写类型" value={kind} onChange={(event) => setKind(event.target.value)} sx={{ minWidth: 140 }}>{Object.entries({ text_box: '普通字段', table_cell: '表格单元格', date: '日期', signature: '签字 / 盖章', checkbox: '复选框' }).map(([key, text]) => <MenuItem key={key} value={key}>{text}</MenuItem>)}</TextField>}
          </Stack>
          <Typography variant="body2" color="text.secondary">{bbox ? '已选择区域，可重新拖动调整。也可用下方数值微调。' : '请在原页上框出需要填写的空白区域。'}</Typography>
          {page && <Box sx={{ position: 'relative', border: '1px solid', borderColor: 'divider', lineHeight: 0, bgcolor: '#FFF' }}>
            <img src={`/api/v2/pages/${page.id}/image`} alt={`第 ${page.page_index + 1} 页原始模板，拖动选择填写区域`} style={{ width: '100%', display: 'block' }} draggable={false} />
            <svg viewBox={`0 0 ${page.width} ${page.height}`} aria-label="框选填写区域" style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', cursor: 'crosshair', touchAction: 'none' }}
              onPointerDown={(event) => {
                if (event.button !== 0) return;
                event.currentTarget.setPointerCapture(event.pointerId);
                const start = point(event); setAnchor(start); setBbox([...start, ...start]);
              }}
              onPointerMove={(event) => {
                if (!anchor) return;
                const end = point(event);
                setBbox([Math.min(anchor[0], end[0]), Math.min(anchor[1], end[1]), Math.max(anchor[0], end[0]), Math.max(anchor[1], end[1])]);
              }}
              onPointerUp={() => setAnchor(null)}
              onPointerCancel={() => setAnchor(null)}>
              {bbox && <rect x={bbox[0]} y={bbox[1]} width={bbox[2] - bbox[0]} height={bbox[3] - bbox[1]} fill="rgba(183,67,43,.15)" stroke="#B7432B" strokeWidth={2} />}
            </svg>
          </Box>}
          {bbox && <Stack direction="row" gap={1}>{['左', '上', '右', '下'].map((text, index) => <TextField key={text} type="number" label={text} value={Math.round(bbox[index] * 10) / 10} inputProps={{ step: 1, min: 0 }} onChange={(event) => setBbox((current) => current!.map((value, position) => position === index ? Number(event.target.value) : value))} />)}</Stack>}
        </Stack>
      </DialogContent>
      <DialogActions><Button onClick={onClose}>取消</Button><Button variant="contained" disabled={!label.trim() || !bbox || bbox[2] <= bbox[0] || bbox[3] <= bbox[1] || save.isPending || Boolean(anchor)} onClick={() => save.mutate()}>保存填写位置</Button></DialogActions>
    </Dialog>
  );
}
