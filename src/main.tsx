import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { Provider } from 'react-redux';
import { store } from './store';
import { setCsrfFallback } from './api';
import App from './App';
import './notifications.css';

// Шаблон /notifications/: <div id="alterlit-notifications" data-csrf="{{ csrf_token }}"></div>
const rootEl = document.getElementById('alterlit-notifications');
if (rootEl) {
  setCsrfFallback(rootEl.dataset.csrf ?? '');
  createRoot(rootEl).render(
    <StrictMode>
      <Provider store={store}>
        <App />
      </Provider>
    </StrictMode>,
  );
}
