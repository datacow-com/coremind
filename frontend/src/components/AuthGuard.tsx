import { Navigate, useLocation } from "react-router-dom";
import { useAuthStore } from "@/store/auth";

const AuthGuard: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const token = useAuthStore((s) => s.token);
  const location = useLocation();

  if (!token) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <>{children}</>;
};

export default AuthGuard;
