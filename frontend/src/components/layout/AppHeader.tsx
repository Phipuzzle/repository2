import { Avatar, Button, Dropdown, Space, Tag, Typography } from "antd";
import { HistoryOutlined, PlusOutlined, SettingOutlined, UserOutlined } from "@ant-design/icons";

interface AppHeaderProps {
  onNew: () => void;
  onHistory: () => void;
}

export function AppHeader({ onNew, onHistory }: AppHeaderProps) {
  return (
    <header className="app-header">
      <Space size="middle">
        <span className="brand-mark">IDA</span>
        <Typography.Title level={4} className="brand-title">Intelligent Data Agent</Typography.Title>
        <Tag color="blue">Mock 工作区</Tag>
      </Space>
      <Space>
        <Button icon={<PlusOutlined />} onClick={onNew}>新建查询</Button>
        <Button icon={<HistoryOutlined />} onClick={onHistory}>历史</Button>
        <Dropdown menu={{ items: [{ key: "profile", label: "alex@example.com", icon: <UserOutlined /> }, { key: "settings", label: "设置", icon: <SettingOutlined /> }] }}>
          <Button type="text" aria-label="用户菜单"><Avatar size="small">A</Avatar></Button>
        </Dropdown>
      </Space>
    </header>
  );
}
