import {defineConfig} from 'vite';
export default defineConfig({base:'./',build:{rollupOptions:{output:{manualChunks:{charts:['echarts'],terminal:['@xterm/xterm','@xterm/addon-fit'],react:['react','react-dom']}}}}});
