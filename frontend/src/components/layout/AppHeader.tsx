import { Avatar, Button, Dropdown, Space, Tag, Typography } from "antd";
import {
  HistoryOutlined,
  LogoutOutlined,
  PlusOutlined,
  SettingOutlined,
  UserOutlined,
} from "@ant-design/icons";

interface AppHeaderProps {
  userLabel: string;
  onNew: () => void;
  onHistory: () => void;
  onSignOut: () => void;
}

export function AppHeader({
  userLabel,
  onNew,
  onHistory,
  onSignOut,
}: AppHeaderProps) {
  return (
    <header className="app-header">
      <Space size="middle">
        <span className="brand-mark">IDA</span>
        <Typography.Title level={4} className="brand-title">
          Intelligent Data Agent
        </Typography.Title>
        <Tag color="blue">API 实时</Tag>
      </Space>
      <Space>
        <Button icon={<PlusOutlined />} onClick={onNew}>
          新建查询
        </Button>
        <Button icon={<HistoryOutlined />} onClick={onHistory}>
          历史
        </Button>
        <Dropdown
          menu={{
            items: [
              {
                key: "profile",
                label: userLabel,
                icon: <UserOutlined />,
                disabled: true,
              },
              {
                key: "settings",
                label: "设置",
                icon: <SettingOutlined />,
                disabled: true,
              },
              { type: "divider" },
              { key: "logout", label: "退出登录", icon: <LogoutOutlined /> },
            ],
            onClick: ({ key }) => {
              if (key === "logout") onSignOut();
            },
          }}
        >
          <Button type="text" aria-label="用户菜单">
            <Avatar size="small">{userLabel.slice(0, 1).toUpperCase()}</Avatar>
          </Button>
        </Dropdown>
      </Space>
    </header>
  );
}
