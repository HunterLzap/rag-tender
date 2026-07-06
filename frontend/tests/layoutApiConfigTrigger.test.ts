import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  API_CONFIG_HOTSPOT_SIZE,
  getApiConfigHotspotSx,
  getApiConfigButtonSx,
} from '../src/components/layoutApiConfigTrigger.ts';

test('API 配置热区固定在页面右上角且不参与布局', () => {
  const sx = getApiConfigHotspotSx();
  assert.equal(sx.position, 'fixed');
  assert.equal(sx.top, 0);
  assert.equal(sx.right, 0);
  assert.equal(sx.width, API_CONFIG_HOTSPOT_SIZE);
  assert.equal(sx.height, API_CONFIG_HOTSPOT_SIZE);
  assert.equal(sx.zIndex, 1300);
});

test('API 配置按钮默认隐藏，键盘聚焦时显示', () => {
  const sx = getApiConfigButtonSx();
  assert.equal(sx.opacity, 0);
  assert.equal(sx.pointerEvents, 'auto');
  assert.equal(sx['&:focus-visible'].opacity, 1);
});

test('API 配置按钮可由热区状态显式显示', () => {
  const sx = getApiConfigButtonSx(true);
  assert.equal(sx.opacity, 1);
});
