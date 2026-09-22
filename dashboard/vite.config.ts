import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 상대 경로(base "./")로 빌드해야 file:// 또는 아무 정적 서버의 하위 경로에서도 열린다.
// 라우팅은 해시(#/mechanical) 라 서버 설정이 필요 없다.
export default defineConfig({
  plugins: [react()],
  base: "./",
  build: {
    outDir: "dist",
    emptyOutDir: true,
    // 영상(public/media)은 그대로 복사된다. ECharts 는 번들에 포함되어 CDN 이 필요 없다.
    chunkSizeWarningLimit: 1500,
  },
  server: { port: 5173 },
  preview: { port: 4173 },
});
