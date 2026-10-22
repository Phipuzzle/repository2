SEMANTIC_METRICS = [
    {
        "name": "销售额",
        "aliases": ["销售额", "营收", "成交额", "金额", "收入"],
        "formula": "SUM(analytics.demo_orders.total_amount)",
        "qualifier": "status = 'paid'",
        "default_grain": "month",
        "chart_type": "line",
    },
    {
        "name": "订单数",
        "aliases": ["订单数", "单量", "订单量", "成交单数"],
        "formula": "COUNT(analytics.demo_orders.id)",
        "qualifier": "status = 'paid'",
        "default_grain": "month",
        "chart_type": "line",
    },
    {
        "name": "退款金额",
        "aliases": ["退款金额", "退款额", "退款"],
        "formula": "SUM(analytics.demo_orders.total_amount)",
        "qualifier": "status = 'refunded'",
        "default_grain": "month",
        "chart_type": "line",
    },
    {
        "name": "平均订单金额",
        "aliases": ["平均订单金额", "客单价", "平均客单价"],
        "formula": "AVG(analytics.demo_orders.total_amount)",
        "qualifier": "status = 'paid'",
        "default_grain": "region",
        "chart_type": "bar",
    },
]

SEMANTIC_DIMENSIONS = [
    {
        "name": "区域",
        "aliases": ["区域", "地区", "大区"],
        "table_name": "demo_regions",
        "column_name": "name",
        "dimension_type": "categorical",
    },
    {
        "name": "商品",
        "aliases": ["商品", "产品", "商品名称"],
        "table_name": "demo_products",
        "column_name": "name",
        "dimension_type": "categorical",
    },
    {
        "name": "商品类别",
        "aliases": ["商品类别", "类目", "品类", "分类"],
        "table_name": "demo_products",
        "column_name": "category",
        "dimension_type": "categorical",
    },
    {
        "name": "月份",
        "aliases": ["月份", "按月", "月度", "每月"],
        "table_name": "demo_orders",
        "column_name": "created_at",
        "dimension_type": "time",
        "time_grain": "month",
    },
    {
        "name": "年份",
        "aliases": ["年份", "按年", "年度", "每年"],
        "table_name": "demo_orders",
        "column_name": "created_at",
        "dimension_type": "time",
        "time_grain": "year",
    },
    {
        "name": "订单状态",
        "aliases": ["状态", "订单状态"],
        "table_name": "demo_orders",
        "column_name": "status",
        "dimension_type": "categorical",
    },
]

SEMANTIC_MAPPINGS = [
    ("销售额", ["区域", "商品", "商品类别", "月份", "年份"]),
    ("订单数", ["区域", "商品", "商品类别", "月份", "年份", "订单状态"]),
    ("退款金额", ["区域", "商品", "商品类别", "月份", "年份"]),
    ("平均订单金额", ["区域", "商品", "商品类别", "月份", "年份"]),
]
