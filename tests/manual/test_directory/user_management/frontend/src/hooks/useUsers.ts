import { useState, useCallback } from 'react';
import { User } from '../types/user';
import { apiClient } from '../utils/apiClient';

interface UseUsersReturn {
  users: User[];
  loading: boolean;
  error: string | null;
  fetchUsers: (page?: number) => Promise<void>;
  deleteUser: (userId: number) => Promise<void>;
}

export const useUsers = (): UseUsersReturn => {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchUsers = useCallback(async (page: number = 1) => {
    setLoading(true);
    setError(null);

    try {
      const response = await apiClient.get(`/api/users?page=${page}&per_page=20`);
      setUsers(response.data.users);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch users');
    } finally {
      setLoading(false);
    }
  }, []);

  const deleteUser = useCallback(async (userId: number) => {
    try {
      await apiClient.delete(`/api/users/${userId}`);
      setUsers(users => users.filter(u => u.id !== userId));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete user');
      throw err;
    }
  }, []);

  return {
    users,
    loading,
    error,
    fetchUsers,
    deleteUser
  };
};
