import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const AuthContext = createContext(null);

export const api = axios.create({ baseURL: `${BACKEND_URL}/api` });

api.interceptors.request.use(config => {
  const token = localStorage.getItem('agripos_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  res => res,
  err => {
    if (err.response?.status === 401) {
      localStorage.removeItem('agripos_token');
      localStorage.removeItem('agripos_user');
      window.location.href = '/login';
    }
    return Promise.reject(err);
  }
);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('agripos_token'));
  const [loading, setLoading] = useState(true);
  const [currentBranch, setCurrentBranch] = useState(null);
  const [branches, setBranches] = useState([]);

  const fetchUser = useCallback(async () => {
    if (!token) { setLoading(false); return; }
    try {
      const res = await api.get('/auth/me');
      setUser(res.data);
      const branchRes = await api.get('/branches');
      setBranches(branchRes.data);
      const savedBranch = localStorage.getItem('agripos_branch');
      if (savedBranch) {
        const found = branchRes.data.find(b => b.id === savedBranch);
        if (found) setCurrentBranch(found);
        else if (branchRes.data.length) setCurrentBranch(branchRes.data[0]);
      } else if (branchRes.data.length) {
        setCurrentBranch(branchRes.data[0]);
      }
    } catch {
      localStorage.removeItem('agripos_token');
      setToken(null);
    }
    setLoading(false);
  }, [token]);

  useEffect(() => { fetchUser(); }, [fetchUser]);

  const login = async (username, password) => {
    const res = await api.post('/auth/login', { username, password });
    localStorage.setItem('agripos_token', res.data.token);
    setToken(res.data.token);
    setUser(res.data.user);
    return res.data;
  };

  const logout = () => {
    localStorage.removeItem('agripos_token');
    localStorage.removeItem('agripos_user');
    localStorage.removeItem('agripos_branch');
    setToken(null);
    setUser(null);
    setCurrentBranch(null);
  };

  const switchBranch = (branch) => {
    setCurrentBranch(branch);
    localStorage.setItem('agripos_branch', branch.id);
  };

  const hasPerm = (module, action) => {
    if (!user) return false;
    if (user.role === 'admin') return true;
    return user.permissions?.[module]?.[action] || false;
  };

  return (
    <AuthContext.Provider value={{ user, token, loading, login, logout, currentBranch, branches, switchBranch, hasPerm, refreshUser: fetchUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
