# 企业差旅报销管理制度 MVP 版

> This file is generated from policy_rules.json. Do not edit manually.

## Policy Metadata

- Policy ID：`company-travel-reimbursement`
- Policy Version：`1.0.0`
- Effective Date：`未提供`
- Currency：`CNY`

## Rules

### R-GEN-001 出差期间消费规则

- 适用类别：ALL
- Enforcement：`ENFORCED`
- Severity：`high`
- Evaluator：`expense_date_within_trip`
- 规则内容：消费日期必须在出差开始日期和出差结束日期之间。
- Keywords：出差期间, 消费日期, 行程日期, 日期异常, 人工复核
- 异常标记：`EXPENSE_OUT_OF_TRIP_DATE`
- 异常说明：消费日期不在出差期间内，需人工复核。

### R-GEN-002 凭证必需规则

- 适用类别：ALL
- Enforcement：`PARTIAL`
- Severity：`high`
- Evaluator：`receipt_presence`
- 规则内容：每笔报销费用原则上必须提供发票、电子发票、支付凭证或其他可验证凭证。当前系统只能可靠判断凭证记录是否存在。
- Keywords：凭证, 发票, 电子发票, 支付凭证, 缺失, 报销凭证
- 异常标记：`RECEIPT_MISSING`
- 异常说明：该笔费用缺少报销凭证。

### R-GEN-003 金额必须大于零

- 适用类别：ALL
- Enforcement：`ENFORCED`
- Severity：`high`
- Evaluator：`positive_amount`
- 规则内容：报销金额必须为正数。
- Keywords：金额, 正数, 无效金额, 报销金额
- Threshold：`GT 0 CNY / PER_EXPENSE`
- 异常标记：`INVALID_AMOUNT`
- 异常说明：报销金额必须大于 0。

### R-TRAFFIC-001 城际交通规则

- 适用类别：交通
- Enforcement：`EVIDENCE_ONLY`
- Severity：`未定义`
- Evaluator：`无`
- 规则内容：高铁、火车、飞机、长途客运等城际交通费用可报销，但费用说明需要与出差行程相关。
- Keywords：交通, 城际交通, 高铁, 火车, 飞机, 机票, 长途客运, 出差行程
- 异常标记：`TRAFFIC_PURPOSE_UNCLEAR`
- 异常说明：交通费用用途不明确，需人工复核。

### R-TRAFFIC-002 市内出行规则

- 适用类别：交通, 市内出行
- Enforcement：`PARTIAL`
- Severity：`medium`
- Evaluator：`amount_threshold`
- 规则内容：出差期间发生的出租车、网约车、地铁等市内出行费用可报销，单笔金额原则上不超过政策定义的市内出行上限。笼统的交通类别不能自动视为市内出行。
- Keywords：交通, 市内出行, 出租车, 网约车, 地铁, 金额, 出差期间
- Threshold：`LTE 300 CNY / PER_EXPENSE`
- 异常标记：`LOCAL_TRAFFIC_AMOUNT_HIGH`
- 异常说明：单笔市内出行费用金额较高，需人工复核。

### R-HOTEL-001 住宿费用上限规则

- 适用类别：住宿
- Enforcement：`PARTIAL`
- Severity：`medium`
- Evaluator：`amount_threshold`
- 规则内容：一线和新一线城市住宿费用原则上不超过政策定义的每晚上限。当前费用数据缺少住宿晚数和费用发生城市，不能直接以整笔金额认定违规。
- Keywords：住宿, 酒店, 金额, 每晚, 超标
- Threshold：`LTE 800 CNY / PER_NIGHT`
- 适用城市：北京, 上海, 广州, 深圳, 杭州, 南京, 苏州, 成都, 重庆, 武汉, 西安, 天津
- 异常标记：`HOTEL_AMOUNT_EXCEED_LIMIT`
- 异常说明：住宿费用超过公司标准，需补充审批说明。

### R-HOTEL-002 住宿凭证规则

- 适用类别：住宿
- Enforcement：`PARTIAL`
- Severity：`未定义`
- Evaluator：`receipt_presence`
- 规则内容：住宿费用必须提供酒店发票或住宿服务类电子发票，且凭证销售方或说明中应能体现住宿服务。当前系统只能可靠判断凭证记录是否存在。
- Keywords：住宿, 酒店发票, 电子发票, 凭证类型, 销售方, 宾馆, 公寓
- 异常标记：`HOTEL_RECEIPT_INVALID`
- 异常说明：住宿凭证类型或销售方信息不明确。

### R-MEAL-001 餐饮费用上限规则

- 适用类别：餐饮
- Enforcement：`ENFORCED`
- Severity：`medium`
- Evaluator：`amount_threshold`
- 规则内容：出差期间餐饮费用可按实际发生报销，但单笔餐饮费用原则上不超过政策定义的餐饮上限。
- Keywords：餐饮, 工作餐, 金额, 超标, 单笔
- Threshold：`LTE 150 CNY / PER_EXPENSE`
- 异常标记：`MEAL_AMOUNT_EXCEED_LIMIT`
- 异常说明：单笔餐饮费用超过标准，需人工复核。

### R-MEAL-002 餐饮凭证规则

- 适用类别：餐饮
- Enforcement：`PARTIAL`
- Severity：`未定义`
- Evaluator：`receipt_presence`
- 规则内容：餐饮费用应提供有效发票或支付凭证。当前系统只能可靠判断凭证记录是否存在。
- Keywords：餐饮, 发票, 支付凭证, 有效凭证, 凭证缺失
- 异常标记：`MEAL_RECEIPT_MISSING`
- 异常说明：餐饮费用缺少凭证。

### R-OTHER-001 其他费用人工复核规则

- 适用类别：其他
- Enforcement：`PARTIAL`
- Severity：`low`
- Evaluator：`manual_review`
- 规则内容：无法明确归类为交通、住宿、餐饮、市内出行的费用应进入人工复核，费用说明需清楚且与出差任务直接相关。
- Keywords：其他, 费用说明, 人工复核, 出差任务, 凭证
- 异常标记：`OTHER_EXPENSE_NEED_REVIEW`
- 异常说明：其他费用需人工确认是否与出差相关。
