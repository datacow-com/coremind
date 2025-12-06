import { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import Button from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { useAuthStore } from "@/store/auth";
import { useToast } from "@/components/ui/toast-provider";

const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { token, baseUrl, setToken, setBaseUrl } = useAuthStore();
  const [value, setValue] = useState(token || "");
  const [apiBase, setApiBase] = useState(baseUrl || "");
  const [msg, setMsg] = useState<string>("");
  const { push } = useToast();

  useEffect(() => {
    if (token) {
      const redirect = (location.state as any)?.from || "/";
      navigate(redirect, { replace: true });
    }
  }, [token, location.state, navigate]);

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!value.trim()) {
      setMsg("请输入后端颁发的 JWT");
      push({ title: "登录失败", description: "缺少 JWT", variant: "error" });
      return;
    }
    setToken(value.trim());
    setBaseUrl(apiBase.trim() || null);
    setMsg("已保存令牌");
    push({ title: "登录成功", description: "令牌已保存", variant: "success" });
    navigate("/", { replace: true });
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-muted">
      <Card className="w-full max-w-md shadow-md">
        <CardHeader>
          <CardTitle>登录 OmniRAG 控制台</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={onSubmit}>
            <div className="space-y-2">
              <Label requiredMark>后端 JWT</Label>
              <Input
                value={value}
                onChange={(e) => setValue(e.target.value)}
                placeholder="粘贴服务器生成的 JWT"
              />
            </div>
            <div className="space-y-2">
              <Label>API 基础地址（可选）</Label>
              <Input
                value={apiBase}
                onChange={(e) => setApiBase(e.target.value)}
                placeholder="例如 https://your-api-host"
              />
              <p className="text-xs text-gray-500">
                留空则使用当前域名，前端会自动拼接 /api 前缀。
              </p>
            </div>
            {msg && <div className="text-xs text-foreground">{msg}</div>}
            <Button className="w-full" type="submit">
              保存并进入
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
};

export default LoginPage;
