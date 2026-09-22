// live/load.ts — JSON/YAML 로더. 문구 파일(YAML)은 빌드에 넣지 않고 런타임에 읽는다 → 발표자가 고치고 새로고침만 하면 반영.
import yaml from "js-yaml";

export async function getJson<T>(path: string): Promise<T> {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`${path} (${r.status}) — export_dashboard_data.py 를 먼저 실행`);
  return r.json();
}
export async function getYaml<T>(path: string): Promise<T> {
  const r = await fetch(path + "?v=" + Date.now());
  if (!r.ok) throw new Error(`${path} (${r.status})`);
  return yaml.load(await r.text()) as T;
}
// 없어도 되는 문구 파일 (예: 용어 풀이)
export async function getYamlOptional<T>(path: string, fallback: T): Promise<T> {
  try { return await getYaml<T>(path); } catch { return fallback; }
}
