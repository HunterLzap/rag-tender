export const API_CONFIG_HOTSPOT_SIZE = 56;

export const getApiConfigHotspotSx = () => ({
  position: 'fixed' as const,
  top: 0,
  right: 0,
  width: API_CONFIG_HOTSPOT_SIZE,
  height: API_CONFIG_HOTSPOT_SIZE,
  zIndex: 1300,
  display: 'flex',
  alignItems: 'flex-start',
  justifyContent: 'flex-end',
  p: 1,
});

export const getApiConfigButtonSx = (visible = false) => ({
  opacity: visible ? 1 : 0,
  pointerEvents: 'auto' as const,
  width: 36,
  height: 36,
  backgroundColor: 'rgba(255, 255, 255, 0.92)',
  color: '#7C4DFF',
  border: '1px solid #EDE7F6',
  boxShadow: '0 4px 12px rgba(124, 77, 255, 0.16)',
  transition: 'opacity 160ms ease, background-color 160ms ease',
  '&:hover': {
    backgroundColor: '#F4EEFF',
  },
  '&:focus-visible': {
    opacity: 1,
  },
});
