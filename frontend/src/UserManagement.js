import React, { useState, useEffect } from 'react';
import './UserManagement.css';

function UserManagement({ token }) {
  const [users, setUsers] = useState([]);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showResetPasswordModal, setShowResetPasswordModal] = useState(false);
  const [selectedUser, setSelectedUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const [newUser, setNewUser] = useState({
    username: '',
    email: '',
    password: '',
    role: 'regular'
  });

  const [resetPassword, setResetPassword] = useState('');

  useEffect(() => {
    fetchUsers();
  }, []);

  const fetchUsers = async () => {
    try {
      const response = await fetch('/api/users', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const usersData = await response.json();
        setUsers(usersData);
      } else {
        setError('Failed to fetch users');
      }
    } catch (err) {
      setError('Network error');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateUser = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const response = await fetch('/api/users', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(newUser),
      });

      if (response.ok) {
        setSuccess('User created successfully');
        setShowCreateModal(false);
        setNewUser({ username: '', email: '', password: '', role: 'regular' });
        fetchUsers();
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to create user');
      }
    } catch (err) {
      setError('Network error');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateUser = async (userId, userData) => {
    try {
      const response = await fetch(`/api/users/${userId}`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(userData),
      });

      if (response.ok) {
        setSuccess('User updated successfully');
        fetchUsers();
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to update user');
      }
    } catch (err) {
      setError('Network error');
    }
  };

  const handleDeleteUser = async (userId, username) => {
    if (window.confirm(`Are you sure you want to deactivate user "${username}"?`)) {
      try {
        const response = await fetch(`/api/users/${userId}`, {
          method: 'DELETE',
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        });

        if (response.ok) {
          setSuccess('User deactivated successfully');
          fetchUsers();
        } else {
          const errorData = await response.json();
          setError(errorData.detail || 'Failed to deactivate user');
        }
      } catch (err) {
        setError('Network error');
      }
    }
  };

  const handleResetPassword = async (e) => {
    e.preventDefault();
    if (!resetPassword) return;

    try {
      const formData = new FormData();
      formData.append('new_password', resetPassword);

      const response = await fetch(`/api/users/${selectedUser.user_id}/reset-password`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
        body: formData,
      });

      if (response.ok) {
        setSuccess('Password reset successfully');
        setShowResetPasswordModal(false);
        setResetPassword('');
        setSelectedUser(null);
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to reset password');
      }
    } catch (err) {
      setError('Network error');
    }
  };

  const toggleUserStatus = async (user) => {
    await handleUpdateUser(user.user_id, { is_active: !user.is_active });
  };

  const changeUserRole = async (user) => {
    const newRole = user.role === 'administrator' ? 'regular' : 'administrator';
    await handleUpdateUser(user.user_id, { role: newRole });
  };

  if (loading) {
    return <div className="loading">Loading users...</div>;
  }

  return (
    <div className="user-management">
      <div className="user-management-header">
        <h2>User Management</h2>
        <button
          className="create-user-btn"
          onClick={() => setShowCreateModal(true)}
        >
          Create New User
        </button>
      </div>

      {error && (
        <div className="message error-message">
          {error}
          <button onClick={() => setError('')} className="close-btn">×</button>
        </div>
      )}

      {success && (
        <div className="message success-message">
          {success}
          <button onClick={() => setSuccess('')} className="close-btn">×</button>
        </div>
      )}

      <div className="users-table-container">
        <table className="users-table">
          <thead>
            <tr>
              <th>Username</th>
              <th>Email</th>
              <th>Role</th>
              <th>Status</th>
              <th>Created</th>
              <th>Last Login</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.user_id} className={!user.is_active ? 'inactive-user' : ''}>
                <td className="username-cell">{user.username}</td>
                <td>{user.email}</td>
                <td>
                  <span className={`role-badge ${user.role}`}>
                    {user.role}
                  </span>
                </td>
                <td>
                  <span className={`status-badge ${user.is_active ? 'active' : 'inactive'}`}>
                    {user.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td>{new Date(user.created_at).toLocaleDateString()}</td>
                <td>
                  {user.last_login
                    ? new Date(user.last_login).toLocaleDateString()
                    : 'Never'
                  }
                </td>
                <td className="actions-cell">
                  <div className="action-buttons">
                    <button
                      className="action-btn toggle-btn"
                      onClick={() => toggleUserStatus(user)}
                      title={user.is_active ? 'Deactivate user' : 'Activate user'}
                    >
                      {user.is_active ? '🔒' : '🔓'}
                    </button>
                    <button
                      className="action-btn role-btn"
                      onClick={() => changeUserRole(user)}
                      title="Toggle role"
                    >
                      👑
                    </button>
                    <button
                      className="action-btn reset-btn"
                      onClick={() => {
                        setSelectedUser(user);
                        setShowResetPasswordModal(true);
                      }}
                      title="Reset password"
                    >
                      🔑
                    </button>
                    <button
                      className="action-btn delete-btn"
                      onClick={() => handleDeleteUser(user.user_id, user.username)}
                      title="Delete user"
                    >
                      🗑️
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Create User Modal */}
      {showCreateModal && (
        <div className="modal-overlay">
          <div className="modal">
            <div className="modal-header">
              <h3>Create New User</h3>
              <button
                className="close-modal-btn"
                onClick={() => setShowCreateModal(false)}
              >
                ×
              </button>
            </div>
            <form onSubmit={handleCreateUser} className="user-form">
              <div className="form-group">
                <label>Username</label>
                <input
                  type="text"
                  value={newUser.username}
                  onChange={(e) => setNewUser({ ...newUser, username: e.target.value })}
                  required
                />
              </div>
              <div className="form-group">
                <label>Email</label>
                <input
                  type="email"
                  value={newUser.email}
                  onChange={(e) => setNewUser({ ...newUser, email: e.target.value })}
                  required
                />
              </div>
              <div className="form-group">
                <label>Password</label>
                <input
                  type="password"
                  value={newUser.password}
                  onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
                  required
                />
              </div>
              <div className="form-group">
                <label>Role</label>
                <select
                  value={newUser.role}
                  onChange={(e) => setNewUser({ ...newUser, role: e.target.value })}
                >
                  <option value="regular">Regular</option>
                  <option value="administrator">Administrator</option>
                </select>
              </div>
              <div className="modal-actions">
                <button type="button" onClick={() => setShowCreateModal(false)}>
                  Cancel
                </button>
                <button type="submit" disabled={loading}>
                  {loading ? 'Creating...' : 'Create User'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Reset Password Modal */}
      {showResetPasswordModal && selectedUser && (
        <div className="modal-overlay">
          <div className="modal">
            <div className="modal-header">
              <h3>Reset Password for {selectedUser.username}</h3>
              <button
                className="close-modal-btn"
                onClick={() => {
                  setShowResetPasswordModal(false);
                  setSelectedUser(null);
                  setResetPassword('');
                }}
              >
                ×
              </button>
            </div>
            <form onSubmit={handleResetPassword} className="user-form">
              <div className="form-group">
                <label>New Password</label>
                <input
                  type="password"
                  value={resetPassword}
                  onChange={(e) => setResetPassword(e.target.value)}
                  required
                  placeholder="Enter new password"
                />
              </div>
              <div className="modal-actions">
                <button
                  type="button"
                  onClick={() => {
                    setShowResetPasswordModal(false);
                    setSelectedUser(null);
                    setResetPassword('');
                  }}
                >
                  Cancel
                </button>
                <button type="submit">
                  Reset Password
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default UserManagement;