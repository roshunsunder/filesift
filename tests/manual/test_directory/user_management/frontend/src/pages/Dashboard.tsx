import React, { useEffect, useState } from 'react';
import { UserCard } from '../components/UserCard';
import { useUsers } from '../hooks/useUsers';
import { User } from '../types/user';
import { LoadingSpinner } from '../components/LoadingSpinner';

export const Dashboard: React.FC = () => {
  const { users, loading, error, fetchUsers, deleteUser } = useUsers();
  const [page, setPage] = useState(1);
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    fetchUsers(page);
  }, [page]);

  const filteredUsers = users.filter(user =>
    user.username.toLowerCase().includes(searchTerm.toLowerCase()) ||
    user.email.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handleDelete = async (userId: number) => {
    try {
      await deleteUser(userId);
      fetchUsers(page);
    } catch (err) {
      console.error('Failed to delete user:', err);
    }
  };

  if (loading) return <LoadingSpinner />;
  if (error) return <div className="error-message">{error}</div>;

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <h1>User Management Dashboard</h1>
        <input
          type="text"
          placeholder="Search users..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="search-input"
        />
      </header>

      <div className="user-grid">
        {filteredUsers.map(user => (
          <UserCard
            key={user.id}
            user={user}
            onDelete={handleDelete}
          />
        ))}
      </div>

      <div className="pagination">
        <button
          onClick={() => setPage(p => Math.max(1, p - 1))}
          disabled={page === 1}
        >
          Previous
        </button>
        <span>Page {page}</span>
        <button onClick={() => setPage(p => p + 1)}>
          Next
        </button>
      </div>
    </div>
  );
};
