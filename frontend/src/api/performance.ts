import client from './client';
import type { PerformanceProject, PerformanceProjectInput } from '../types';

export async function getPerformanceProjects(): Promise<PerformanceProject[]> {
  const res = await client.get<PerformanceProject[]>('/performance/projects');
  return res.data;
}

export async function createPerformanceProject(
  data: PerformanceProjectInput,
): Promise<PerformanceProject> {
  const res = await client.post<PerformanceProject>('/performance/projects', data);
  return res.data;
}

export async function updatePerformanceProject(
  id: number,
  data: Partial<PerformanceProjectInput>,
): Promise<PerformanceProject> {
  const res = await client.put<PerformanceProject>(`/performance/projects/${id}`, data);
  return res.data;
}

export async function deletePerformanceProject(id: number): Promise<{ deleted: boolean }> {
  const res = await client.delete<{ deleted: boolean }>(`/performance/projects/${id}`);
  return res.data;
}
