import React, { useCallback, useEffect, useState } from 'react';
import {
  Box,
  Tab,
  Tabs,
  CircularProgress,
  Typography,
  Alert,
} from '@mui/material';

import MatchResultTable from './MatchResultTable';
import TechnicalResponseTable from './TechnicalResponseTable';
import SubmissionChecklistTable from './SubmissionChecklistTable';
import { getTechnicalResponses } from '../api/technical';
import { getChecklist } from '../api/checklist';
import type {
  MatchResult,
  MatchStatus,
  SubmissionChecklist,
  TechnicalResponse,
} from '../types';

interface MatchResultTabsProps {
  tenderId: number;
  matchResults: MatchResult[];
  onConfirm: (matchId: number, status: MatchStatus, correctionReason?: string) => void;
}

/**
 * Three-tab container for match results page (Q6 decision).
 *
 * Tab 1: 企业资质匹配 — capability class match results (MatchResultTable)
 * Tab 2: 技术响应表 — product_spec class requirements (TechnicalResponseTable)
 * Tab 3: 投标待办清单 — submission class requirements (SubmissionChecklistTable)
 *
 * Data for Tab 2 and Tab 3 is fetched on first access and cached in component state
 * (decision #7). Manual edits update the cache locally.
 */
const MatchResultTabs: React.FC<MatchResultTabsProps> = ({
  tenderId,
  matchResults,
  onConfirm,
}) => {
  const [activeTab, setActiveTab] = useState(0);
  const [technicalResponses, setTechnicalResponses] = useState<
    TechnicalResponse[] | null
  >(null);
  const [checklist, setChecklist] = useState<SubmissionChecklist[] | null>(
    null,
  );
  const [loadingTab, setLoadingTab] = useState(false);
  const [tabError, setTabError] = useState<string | null>(null);

  const handleTabChange = useCallback(
    async (_event: React.SyntheticEvent, newTab: number) => {
      setActiveTab(newTab);
      setTabError(null);

      // Fetch technical responses on first access of Tab 1
      if (newTab === 1 && technicalResponses === null) {
        setLoadingTab(true);
        try {
          const data = await getTechnicalResponses(tenderId);
          setTechnicalResponses(data);
        } catch (err) {
          setTabError(
            err instanceof Error ? err.message : '加载技术响应表失败',
          );
        } finally {
          setLoadingTab(false);
        }
      }

      // Fetch checklist on first access of Tab 2
      if (newTab === 2 && checklist === null) {
        setLoadingTab(true);
        try {
          const data = await getChecklist(tenderId);
          setChecklist(data);
        } catch (err) {
          setTabError(
            err instanceof Error ? err.message : '加载待办清单失败',
          );
        } finally {
          setLoadingTab(false);
        }
      }
    },
    [tenderId, technicalResponses, checklist],
  );

  // Reset cached data when tender changes
  useEffect(() => {
    setTechnicalResponses(null);
    setChecklist(null);
    setActiveTab(0);
  }, [tenderId]);

  return (
    <Box>
      <Tabs
        value={activeTab}
        onChange={handleTabChange}
        sx={{
          borderBottom: '1px solid #EDE7F6',
          mb: 2,
          '& .MuiTab-root': {
            color: '#666',
            fontWeight: 600,
            textTransform: 'none',
            '&.Mui-selected': { color: '#7C4DFF' },
          },
          '& .MuiTabs-indicator': { backgroundColor: '#7C4DFF' },
        }}
      >
        <Tab label="企业资质匹配" />
        <Tab label="技术响应表" />
        <Tab label="投标待办清单" />
      </Tabs>

      {tabError && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setTabError(null)}>
          {tabError}
        </Alert>
      )}

      {/* Tab 0: 企业资质匹配 — results already filtered by backend _should_match() */}
      {activeTab === 0 && (
        <MatchResultTable results={matchResults} onConfirm={onConfirm} />
      )}

      {/* Tab 1: 技术响应表 */}
      {activeTab === 1 && (
        <>
          {loadingTab ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
              <CircularProgress sx={{ color: '#7C4DFF' }} />
            </Box>
          ) : technicalResponses !== null ? (
            <TechnicalResponseTable
              tenderId={tenderId}
              responses={technicalResponses}
              onUpdate={(updated) => {
                setTechnicalResponses((prev) =>
                  prev
                    ? prev.map((r) =>
                        r.id === updated.id ? updated : r,
                      )
                    : prev,
                );
              }}
            />
          ) : (
            <Typography sx={{ color: '#999', py: 4, textAlign: 'center' }}>
              加载失败，请切换 Tab 重试
            </Typography>
          )}
        </>
      )}

      {/* Tab 2: 投标待办清单 */}
      {activeTab === 2 && (
        <>
          {loadingTab ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
              <CircularProgress sx={{ color: '#7C4DFF' }} />
            </Box>
          ) : checklist !== null ? (
            <SubmissionChecklistTable
              tenderId={tenderId}
              items={checklist}
              onUpdate={(updated) => {
                setChecklist((prev) =>
                  prev
                    ? prev.map((item) =>
                        item.id === updated.id ? updated : item,
                      )
                    : prev,
                );
              }}
              onAdd={(newItem) => {
                setChecklist((prev) => (prev ? [...prev, newItem] : [newItem]));
              }}
            />
          ) : (
            <Typography sx={{ color: '#999', py: 4, textAlign: 'center' }}>
              加载失败，请切换 Tab 重试
            </Typography>
          )}
        </>
      )}
    </Box>
  );
};

export default MatchResultTabs;
