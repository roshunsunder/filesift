import React from 'react';
import { User } from '../types/user';
import './UserCard.css';

interface UserCardProps {
  user: User;
  onEdit?: (user: User) => void;
  onDelete?: (userId: number) => void;
}

export const UserCard: React.FC<UserCardProps> = ({ user, onEdit, onDelete }) => {
  const handleEdit = () => {
    if (onEdit) {
      onEdit(user);
    }
  };

  const handleDelete = () => {
    if (onDelete && window.confirm(`Are you sure you want to delete ${user.username}?`)) {
      onDelete(user.id);
    }
  };

  return (
    <div className="user-card">
      <div className="user-card__header">
        <h3>{user.username}</h3>
        <span className={`status-badge ${user.is_active ? 'active' : 'inactive'}`}>
          {user.is_active ? 'Active' : 'Inactive'}
        </span>
      </div>
      <div className="user-card__body">
        <p className="user-email">{user.email}</p>
        <p className="user-joined">
          Joined: {new Date(user.created_at).toLocaleDateString()}
        </p>
      </div>
      <div className="user-card__actions">
        <button onClick={handleEdit} className="btn btn-primary">
          Edit
        </button>
        <button onClick={handleDelete} className="btn btn-danger">
          Delete
        </button>
      </div>
    </div>
  );
};
