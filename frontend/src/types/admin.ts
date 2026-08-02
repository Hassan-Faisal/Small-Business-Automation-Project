export interface AdminProfile {
  id: number;
  full_name: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  last_login_at: string | null;
}

export interface AuthResponse {
  message: string;
  admin: AdminProfile;
}