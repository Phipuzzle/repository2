import { Button, Empty, Space, Table, Tooltip, Typography } from "antd";
import { DownloadOutlined } from "@ant-design/icons";
import type { QueryResult } from "../../features/query-run/types";

export function DataTable({ result }: { result: QueryResult | null }) {
  if (!result || result.rows.length === 0)
    return (
      <div className="result-empty">
        <Empty description="没有匹配的数据" />
      </div>
    );
  const exportCsv = () => {
    const header = result.schema.map((field) => field.label).join(",");
    const rows = result.rows.map((row) =>
      result.schema
        .map((field) => JSON.stringify(row[field.name] ?? ""))
        .join(","),
    );
    const blob = new Blob([[header, ...rows].join("\n")], {
      type: "text/csv;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "query-result.csv";
    link.click();
    URL.revokeObjectURL(url);
  };
  const columns = result.schema.map((field) => ({
    title: field.label,
    dataIndex: field.name,
    key: field.name,
    filters: [...new Set(result.rows.map((row) => row[field.name]))]
      .slice(0, 20)
      .map((value) => ({ text: String(value), value: String(value) })),
    onFilter: (
      value: boolean | React.Key,
      record: Record<string, string | number | boolean | null>,
    ) => String(record[field.name]) === String(value),
    sorter: (
      left: Record<string, string | number | boolean | null>,
      right: Record<string, string | number | boolean | null>,
    ) => {
      const a = left[field.name];
      const b = right[field.name];
      return typeof a === "number" && typeof b === "number"
        ? a - b
        : String(a).localeCompare(String(b), "zh-CN");
    },
    render: (value: string | number | boolean | null) =>
      value === null
        ? "—"
        : field.type === "number"
          ? Number(value).toLocaleString("zh-CN")
          : String(value),
  }));
  const dataSource = result.rows.map((row, index) => ({
    ...row,
    key: `${index}:${JSON.stringify(row)}`,
  }));
  return (
    <section aria-label="查询结果数据表">
      <div className="section-title">
        <Typography.Text strong>结果数据</Typography.Text>
        <Space>
          <Typography.Text type="secondary">
            共 {result.total} 行
          </Typography.Text>
          <Tooltip title="导出 CSV">
            <Button
              type="text"
              size="small"
              icon={<DownloadOutlined />}
              aria-label="导出 CSV"
              onClick={exportCsv}
            />
          </Tooltip>
        </Space>
      </div>
      <Table
        size="small"
        pagination={{ pageSize: 5, showSizeChanger: false }}
        scroll={{ x: "max-content" }}
        rowKey="key"
        columns={columns}
        dataSource={dataSource}
      />
    </section>
  );
}
