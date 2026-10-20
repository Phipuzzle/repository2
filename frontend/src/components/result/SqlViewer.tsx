import { Button, Empty, Typography } from "antd";
import { CopyOutlined } from "@ant-design/icons";

export function SqlViewer({ sql }: { sql: string }) {
  if (!sql) return <div className="result-empty"><Empty description="等待 SQL 生成" /></div>;
  return <section className="sql-viewer"><div className="section-title"><Typography.Text strong>只读 SQL</Typography.Text><Button icon={<CopyOutlined />} onClick={() => void navigator.clipboard?.writeText(sql)}>复制</Button></div><pre>{sql}</pre></section>;
}
