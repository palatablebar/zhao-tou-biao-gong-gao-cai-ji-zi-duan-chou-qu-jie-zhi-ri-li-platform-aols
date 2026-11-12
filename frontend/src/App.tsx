import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import AppRouter from './router';
import { authStore } from './stores/authStore';

export default function App() {
  const location = useLocation();
  useEffect(() => {
    authStore.bootstrap();
  }, []);
  return <AppRouter key={location.pathname.startsWith('/login') ? 'auth' : 'app'} />;
}
