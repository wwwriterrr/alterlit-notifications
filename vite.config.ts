import type { ServerResponse } from 'node:http';
import { defineConfig, loadEnv, type ProxyOptions } from 'vite';
import react from '@vitejs/plugin-react';

/**
 * Dev: /api/v1/notifications/ — либо заглушки (DEV_FIXTURES=1 в .env.local и `npm run fixtures`:
 * тот же разбор и группировка, что на сервере), либо прод через прокси с DEV_COOKIE.
 * С прода по умолчанию только чтение: «прочитать» и «удалить» — при DEV_ALLOW_WRITE=1.
 */
export default defineConfig(({ mode, command }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const backend = (env.BACKEND_URL || 'https://alterlit.ru').replace(/\/$/, '');
  const asAdmin = env.DEV_AS === 'admin' && Boolean(env.DEV_COOKIE_ADMIN);
  const devCookie = (asAdmin ? env.DEV_COOKIE_ADMIN : env.DEV_COOKIE) || '';
  const csrf = /(?:^|;\s*)csrftoken=([^;]+)/.exec(devCookie)?.[1];
  if (command === 'serve') {
    console.log(env.DEV_FIXTURES ? '  уведомления: заглушки 127.0.0.1:5186' : `  уведомления: ${backend} (${asAdmin ? 'администратор' : 'пользователь'})`);
  }

  const proxy = (target = backend): ProxyOptions => ({
    target,
    changeOrigin: true,
    secure: true,
    configure: (p) => {
      p.on('proxyReq', (req, inReq, res) => {
        if (target !== backend) return;
        if (inReq.method !== 'GET' && inReq.url?.startsWith('/api/v1/notifications/') && !env.DEV_ALLOW_WRITE) {
          const r = res as ServerResponse;
          r.statusCode = 403;
          r.setHeader('content-type', 'application/json');
          r.end(JSON.stringify({ detail: 'dev: запись на прод выключена (DEV_ALLOW_WRITE=1 в .env.local)' }));
          req.destroy();
          return;
        }
        if (!devCookie) return;
        req.setHeader('cookie', devCookie);
        req.setHeader('origin', backend);
        req.setHeader('referer', backend + '/');
        if (csrf) req.setHeader('x-csrftoken', csrf);
      });
      p.on('proxyRes', (res) => {
        delete res.headers['set-cookie'];
      });
    },
  });

  return {
    // статику отдаёт Django с /assets/notifications/
    base: command === 'build' ? env.VITE_ASSETS_BASE || '/assets/notifications/' : '/',
    plugins: [react()],
    build: {
      outDir: 'dist',
      emptyOutDir: true,
      cssCodeSplit: false,
      rollupOptions: {
        // без index.html: остров подключает шаблон Django
        input: 'src/main.tsx',
        output: {
          // постоянные имена — прописаны в шаблоне (с ?v=)
          entryFileNames: 'notifications.js',
          inlineDynamicImports: true,
          assetFileNames: (info) =>
            info.names?.some((n) => n.endsWith('.css')) ? 'notifications.css' : 'assets/[name]-[hash][extname]',
        },
      },
    },
    server: {
      port: 5185,
      proxy: {
        '/api/v1/notifications': env.DEV_FIXTURES ? proxy('http://127.0.0.1:5186') : proxy(),
        '/api': proxy(),
        '/media': proxy(),
        // статика сайта — для dev-prod.html (страница сайта целиком, со стилями base.html)
        '/assets': proxy(),
        '/static': proxy(),
      },
    },
  };
});
