# 业绩项目库一期设计

## 目标

将“业绩”从普通证书资质里拆出来，建立独立的业绩项目库。先支持手动录入、编辑、删除和关联已上传业绩文件，不做年度总表自动导入、不做合同自动匹配。

## 数据模型

新增 `performance_projects` 表：

- `id`
- `project_name` 项目名称
- `client_name` 甲方/客户
- `contract_no` 合同编号
- `contract_amount` 合同金额
- `sign_date` 签订日期
- `completion_date` 完成/验收日期
- `project_scope` 项目内容/供货范围
- `year` 所属年度
- `file_ids` 关联证明文件 ID，JSON 数组字符串
- `remark`
- `created_at`
- `updated_at`

## 后端接口

新增 `/api/v1/performance/projects`：

- `GET /projects`：列表
- `POST /projects`：新增
- `PUT /projects/{id}`：编辑
- `DELETE /projects/{id}`：删除

## 前端

资质库页新增第三个 Tab：`业绩项目`。

功能：

- 列表展示业绩项目。
- 每页 10 条。
- 新增/编辑弹窗。
- 可关联已上传且分类为 `performance` 的文件。
- 支持删除项目。删除项目不删除源文件。

## 不做

- 不自动解析年度总表。
- 不自动拆合同。
- 不参与标书匹配逻辑改造。
- 不迁移已有普通资质里的业绩数据。
