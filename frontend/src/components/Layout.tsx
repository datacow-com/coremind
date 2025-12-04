import React from "react";
import { Link, Outlet, useLocation } from "react-router-dom";
import { MessageSquare, Database, Search, FolderGit2 } from "lucide-react";

const Layout: React.FC = () => {
  const location = useLocation();

  const navigation = [
    { name: "聊天", href: "/", icon: MessageSquare },
    { name: "知识库", href: "/kb", icon: Database },
    { name: "搜索", href: "/search", icon: Database },
    { name: "文件管理", href: "/files", icon: FolderGit2 },
  ];

  return (
    <div className="flex h-screen bg-background text-foreground">
      <header className="w-full border-b bg-white">
        <div className="max-w-screen-xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
              <Search className="h-5 w-5 text-primary-foreground" />
            </div>
            <span className="text-lg font-semibold">OmniRAG</span>
          </div>
          <nav className="flex items-center space-x-1">
            {navigation.map((item) => {
              const Icon = item.icon;
              const isActive =
                location.pathname === item.href ||
                location.pathname.startsWith(`${item.href}/`);
              return (
                <Link
                  key={item.name}
                  to={item.href}
                  className={`flex items-center space-x-2 px-3 py-2 rounded-md text-sm ${
                    isActive
                      ? "text-primary bg-muted"
                      : "text-gray-700 hover:text-foreground hover:bg-muted"
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  <span>{item.name}</span>
                </Link>
              );
            })}
          </nav>
        </div>
      </header>
      <main className="flex-1 overflow-auto h-[calc(100vh-56px)]">
        <div className="max-w-screen-xl mx-auto px-6 py-6 h-full">
          <Outlet />
        </div>
      </main>
    </div>
  );
};

export default Layout;
