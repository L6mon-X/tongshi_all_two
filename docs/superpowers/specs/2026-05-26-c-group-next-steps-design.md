# C 组（作品与文件存储）— 头脑风暴：下一步做什么

> 日期：2026-05-26
> 负责人：俞（yu1gg）
> 当前项目 commit：739954a（Merge pull request #2 from 66qjc/change）

---

## 总体现状评估

C 组六大功能域的基础骨架已全部搭建完成：

| 功能域 | 状态 | 关键风险 |
|--------|------|----------|
| 作品上传 | 85% — 接口完整，魔数校验基本可用 | MP4/MOV 魔数校验偏弱，`biz_type` 缺失 |
| 教师审核 | 90% — 审核/驳回接口完整 | 前端刷新行为不一致，PDF 预览 CORS 风险 |
| 批量下载 | 50% — 仅支持本地存储，S3 完全不可用 | **严重缺陷**，直接硬编码 `/uploads` 路径 |
| 对象存储接入 | 60% — S3 适配器存在但缺少关键配置 | `force_path_style` 未传递，无重试/错误处理 |
| 历史文件兼容 | 80% — `/uploads/` 静态挂载保留 | 兼容路径判断逻辑脆弱 |
| 上传安全校验 | 85% — 扩展名+魔数框架完整 | MP4/MOV 校验有空隙，SVG 无安全清洗 |

**测试**：39/39 全部通过。但 S3、审核流程、点赞等关键路径无测试覆盖。

---

## 大计划总览

按优先级从高到低排列六个大计划：

| 序号 | 大计划 | 优先级 | 预计影响 |
|------|--------|--------|----------|
| P1 | 批量下载 S3 适配改造 | **紧急** | 修复 S3 模式下批量下载完全不可用 |
| P2 | S3 存储适配器修复 | **紧急** | 修复 `force_path_style` 缺失导致 SeaweedFS 连接失败 |
| P3 | 上传安全校验加固 | 高 | 堵住 MP4/MOV 魔数校验漏洞 |
| P4 | 测试体系补齐 | 高 | S3、审核、点赞、并发场景覆盖 |
| P5 | 前端体验优化 | 中 | `biz_type`、图片预览、审核搜索 |
| P6 | 代码质量与工程化 | 中 | Pydantic schema 落地、事务整理、DRY |

---

## P1 — 批量下载 S3 适配改造

### 现状

`teacher_routes.py` 的 `batch_download` 接口存在三个严重问题：

1. **硬编码本地路径**：`Path(__file__).resolve().parents[4] / "uploads"` 直接读写磁盘，S3 模式下完全找不到文件
2. **未使用 StoredFile 新表**：下载时查询的是 `Project.report_url`（旧字段），而非 `Project.report_file_id`（新字段，指向 `stored_files` 表）
3. **ZIP 全量在内存中打包**：`io.BytesIO()` + `zipfile.ZipFile` 将所有文件读入内存后才返回，学生多时可能爆内存

### 目标状态

1. 批量下载通过 `file_service.resolve_file_stream()` 统一获取文件流，自动适配 local/s3
2. 优先使用 `report_file_id`（新方式）定位文件，fallback 到 `report_url`（旧方式）兜底历史数据
3. 改用 `zipfile.ZipFile` 的流式写入模式 + `StreamingResponse`，不在内存中累积所有文件

### 子计划

#### 1.1 修改批量下载的文件定位逻辑

- **文件**：`backend/app/api/v1/routes/teacher_routes.py` 的 `batch_download` 函数
- **目标**：将文件读取从直接 `open(uploads/...)` 改为调用 `file_service.resolve_file_stream()`
- **现状**：`open(upload_dir / filename, "rb")` — 只读写本地磁盘
- **验证**：`STORAGE_BACKEND=local` 时批量下载 ZIP 正常返回；`STORAGE_BACKEND=s3` 时也能下载（需要 S3 mock）

#### 1.2 统一使用 report_file_id（新）兼容 report_url（旧）

- **文件**：`teacher_routes.py` batch_download + `project_service.py`
- **目标**：遍历 `project.report_file_id` → `stored_files` 获取 `object_key` 和 `storage_provider`，不存在时 fallback 到 `report_url` 本地路径
- **现状**：只用了 `report_url`，报告如果走 S3 上传后 `report_url` 里存的是旧格式路径
- **验证**：用新方式上传的作品能下载；只存了旧 URL 的历史作品也能下载

#### 1.3 流式 ZIP 打包（不爆内存）

- **文件**：`teacher_routes.py` batch_download
- **目标**：使用 `zipstream` 库或自定义生成器，逐个读文件流 → 写 ZIP entry → yield 给 StreamingResponse
- **现状**：所有文件一起 `write()` 到 BytesIO，然后一次性 `getvalue()` 返回
- **关键要求**：不引入重量级依赖，可用纯 Python `zipfile.ZipFile` 配合 `io.BytesIO` 分段 yield
- **验证**：模拟 100 个 10MB 报告打包，内存峰值不超过 50MB

#### 1.4 文件名安全处理增强

- **文件**：`teacher_routes.py` batch_download
- **目标**：增强 `sanitize` 逻辑，处理 Unicode 控制字符、路径遍历字符
- **验证**：包含特殊字符的项目标题不会导致 ZIP 路径异常

---

## P2 — S3 存储适配器修复

### 现状

`storage_s3.py` 存在四个问题：

1. **`s3_force_path_style` 完全未使用**：`config.py` 已定义此配置且默认 `true`，但 boto3 client 创建时没传，对接 SeaweedFS/MinIO 时会连接失败
2. **无初始化连通性检查**：boto3 client 惰性初始化，凭据错误要到第一次调用时才能发现
3. **无重试策略**：临时网络故障直接失败
4. **`open_stream` 无 404 处理**：Key 不存在时抛出未捕获的 ClientError

### 目标状态

1. boto3 client 正确传递 `addressing_style` 配置
2. 初始化时做一次轻量连通性检查（`list_buckets` 或 `head_bucket`）
3. 配置重试策略（默认 3 次）
4. `open_stream` 捕获 `NoSuchKey`，返回明确错误

### 子计划

#### 2.1 传递 s3_force_path_style 到 boto3

- **文件**：`backend/app/services/storage_s3.py`
- **修改点**：在 `boto3.client("s3", ...)` 时传入 `config=Config(s3={"addressing_style": "path"})`
- **目标**：读取 `config.s3_force_path_style`，为 True 时启用 path-style
- **验证**：SeaweedFS 或 MinIO 环境下文件上传下载正常

#### 2.2 添加重试策略

- **文件**：`storage_s3.py`
- **目标**：boto3 client 创建时设置 `retries={"max_attempts": 3, "mode": "standard"}`
- **验证**：模拟临时网络故障，确认重试机制生效

#### 2.3 open_stream 添加 404 错误处理

- **文件**：`storage_s3.py` 的 `open_stream` 方法
- **目标**：捕获 boto3 `ClientError`，若 HTTP 状态码为 404 抛出文件不存在的 BusinessException
- **现状**：直接 raise 未捕获异常 → 500
- **验证**：请求不存在的 S3 文件 ID 时返回友好错误而非 500

#### 2.4 添加初始化连通性检查（可选，低优先级）

- **文件**：`storage_s3.py`
- **目标**：`__init__` 最后调用 `self._client.head_bucket(Bucket=bucket)` 做连通性检查
- **注意**：需要 `head_bucket` 权限，如果 SeaweedFS 不支持此操作则跳过
- **验证**：S3 凭据错误时启动即报错，而非延迟到首次请求

---

## P3 — 上传安全校验加固

### 现状

`upload_validation.py` 的魔数校验框架完整，但 MP4/MOV 的校验逻辑有缺陷：

1. **MP4/MOV 校验存在空子**：前 3 字节为 `\x00\x00\x00` 即通过，任意以三个 null 字节开头的文件都能绕过
2. **WebP 校验只检查 RIFF 头**：未验证偏移 8 处的 `WEBP` 标识，AVI/WAV 可能误过
3. **SVG 无安全清洗**：允许 SVG 上传但不做 XXE/脚本注入过滤
4. **DOC/DOCX 完全跳过魔数**：虽合理（ZIP 容器格式），但可补上 PK 头检查

### 目标状态

1. MP4/MOV 正确校验 ftyp box（偏移 4 处）
2. WebP 校验 RIFF + WEBP 双重标识
3. SVG 上传时做基础安全清洗（移除 script 标签）
4. DOCX 等 ZIP 容器格式检查 PK 头

### 子计划

#### 3.1 修复 MP4/MOV 魔数校验

- **文件**：`backend/app/core/upload_validation.py`
- **目标**：校验前 4 字节为 `\x00\x00\x00\x18`（或 `\x00\x00\x00\x14`、`\x00\x00\x00\x1c` 等），偏移 4 处前 4 字节为 `ftyp`
- **方案**：魔数签名支持 `(offset, bytes)` 元组，偏移 0 的签名先检查，再检查偏移 4 的 `ftyp`
- **讨论**：是否引入偏移量概念？还是改两个独立签名条件？
- **验证**：真实 MP4/MOV 文件通过；全 null 字节文件被拒绝

#### 3.2 修复 WebP 魔数校验

- **文件**：`upload_validation.py`
- **目标**：校验前 4 字节为 `RIFF` AND 偏移 8 处 4 字节为 `WEBP`
- **验证**：真实 WebP 通过；AVI/WAV 文件被拒绝

#### 3.3 SVG 上传安全清洗

- **文件**：新增 `backend/app/core/svg_sanitizer.py`，在 `upload_validation.py` 中调用
- **目标**：上传 SVG 后、入库前做 XML 解析，移除 `<script>`、`on*` 事件属性、`<foreignObject>`、外部实体引用
- **注意**：这一步在"文件内容已保存之后"做，如果清洗失败需要回滚（删除已保存的文件）
- **验证**：含 `<script>` 的 SVG 上传后被清洗干净

#### 3.4 增加 ZIP 容器格式的 PK 头检查

- **文件**：`upload_validation.py`
- **目标**：对 DOCX、PPTX 等 ZIP 容器格式，检查前 2 字节是否为 `PK`
- **验证**：真实 DOCX 通过；篡改扩展名为 .docx 的文本文件被拒绝

---

## P4 — 测试体系补齐

### 现状

39 个测试全部通过。但以下关键路径无测试覆盖：

| 缺失项 | 影响 |
|--------|------|
| S3 适配器（local mock） | 存储切换无回归保障 |
| 作品审核接口 | 审核流程无自动化验证 |
| 作品点赞接口 | 点赞功能无测试 |
| 作品 CRUD 完整流程 | 从创建到展示无 E2E 覆盖 |
| 批量下载 S3 路径 | S3 模式下载无测试 |
| 并发点赞 | 竞态条件无法复现验证 |

### 目标状态

1. `StorageS3Adapter` 有基于 mock（moto 库）的单元测试
2. 审核通过/驳回接口有集成测试
3. 点赞/取消点赞有集成测试
4. 作品创建→展示→审核完整流程有 E2E 测试
5. 批量下载在 local 和 mock S3 两种模式下均通过

### 子计划

#### 4.1 S3 适配器单元测试（moto mock）

- **文件**：新建 `backend/tests/test_storage_s3.py`
- **工具**：`pip install moto[s3]`
- **覆盖**：`save_bytes`、`open_stream`、`exists`、`delete`、`open_stream` 的 404 处理、`force_path_style` 传递验证
- **目标**：不依赖真实 S3 服务即可跑通全部 S3 适配器测试

#### 4.2 审核接口集成测试

- **文件**：`backend/tests/test_integration_bugfixes.py` 追加
- **覆盖**：
  - 教师通过作品审核 → 作品状态变更为 `approved`
  - 教师驳回作品审核（含理由）→ 作品状态变更为 `rejected`，`reject_reason` 不为空
  - 非教师角色审核被拒绝（403）
  - 审核不存在的作品返回 404
  - 重复审核同一作品（幂等性）

#### 4.3 点赞接口集成测试

- **文件**：同上
- **覆盖**：
  - 点赞作品 → likes 数 +1
  - 取消点赞 → likes 数 -1
  - 重复点赞不生效（幂等性）
  - 点赞不存在的作品返回 404

#### 4.4 作品完整流程测试

- **文件**：同上
- **覆盖**：
  - 学生创建作品（含报告 file_id）→ 查询作品广场出现该作品（pending 不出现）→ 教师审核通过 → 广场可见
  - 学生编辑作品重新提交 → 状态从 rejected 变回 pending

#### 4.5 批量下载在两种存储模式下的测试

- **文件**：同上
- **覆盖**：
  - local 模式批量下载返回 ZIP
  - S3 mock 模式批量下载返回 ZIP（P1 改造后）
  - 空结果（无可下载作品）返回合适响应

---

## P5 — 前端体验优化

### 现状

`ProjectUploadView.vue` 和 `TeacherReviews.vue` 功能基本可用，但存在若干体验问题。

### 目标状态

1. 学生上传时明确传递业务类型（`biz_type`），后端能区分作品图片/报告/其他
2. 编辑作品时能预览已上传的图片缩略图
3. 教师审核页面支持关键词搜索和状态筛选切换
4. 前端文件大小限制与后端一致（统一 50MB）
5. 审核后列表刷新行为一致

### 子计划

#### 5.1 上传增加 biz_type 参数

- **文件**：`frontend/src/api/upload.ts` + `frontend/src/views/ProjectUploadView.vue`
- **目标**：调用 `uploadFile` 时传入 `biz_type: "project_image"` 或 `"project_report"`
- **后端兼容**：`upload_routes.py` 接收 `biz_type` 参数，传递给 `create_stored_file_record`
- **验证**：上传作品图片后 `stored_files.biz_type` = `"project_image"`

#### 5.2 图片预览缩略图

- **文件**：`ProjectUploadView.vue`
- **目标**：编辑模式下，已有图片显示缩略图而非纯文字，可点击大图查看
- **验证**：编辑含图片的作品时能看到缩略图

#### 5.3 审核列表搜索与筛选

- **文件**：`TeacherReviews.vue`
- **目标**：
  - 增加搜索框支持按作品名称搜索
  - 增加 status 切换（全部/pending/approved/rejected）调用后端筛选
- **验证**：教师能按状态筛选作品列表

#### 5.4 前端文件大小限制同步

- **文件**：`ProjectUploadView.vue`
- **目标**：将显示文案和校验逻辑改为 50MB（与后端 `MAX_UPLOAD_SIZE` 一致）
- **验证**：前后端大小限制统一

#### 5.5 审核后列表刷新行为统一

- **文件**：`TeacherReviews.vue`
- **目标**：`handleApprove` 也对已通过的作品从列表中移除或统一状态展示，与 `handleReject` 行为一致
- **验证**：通过审核后列表正确更新

---

## P6 — 代码质量与工程化

### 现状

C 组代码可运行但存在技术债：

1. **Pydantic schema 未被路由使用**：所有路由手动构造 dict 返回，Swagger 文档不准确
2. **`_format_project` 重复定义**：`project_routes.py` 和 `teacher_routes.py` 各一份
3. **项目表新旧字段冗余**：`report_url` vs `report_file_id` 并存，数据一致性难维护
4. **sha256 字段形同虚设**：定义了但不计算填充
5. **`ProjectLike` 缺少唯一约束**：靠应用层代码保证，数据库无兜底
6. **并发点赞有竞态条件**：`SELECT + UPDATE` 非原子

### 目标状态

1. 路由返回使用 Pydantic schema，Swagger 文档准确
2. `_format_project` 提取到公共模块
3. 旧字段标记 deprecated，新代码统一用 `file_id`
4. 上传时计算 SHA-256 并入库
5. `ProjectLike` 添加唯一约束
6. 点赞使用 `UPDATE SET likes = likes +/- 1` 原子操作

### 子计划

#### 6.1 路由返回统一使用 Pydantic schema

- **文件**：`project_routes.py`、`teacher_routes.py`、`upload_routes.py`
- **目标**：将手动返回 dict 改为 `ProjectOut.model_validate(project).model_dump()` 或直接返回 Pydantic model
- **影响**：可能改变返回 JSON 的字段名（Python snake_case vs JSON camelCase），需与前端协调
- **验证**：路由返回的 Swagger 文档显示正确 schema；前端数据解析不受影响

#### 6.2 提取公共 _format_project

- **文件**：新建或复用 `backend/app/services/project_service.py`
- **目标**：定义一个 `format_project(project) -> dict` 函数，两个路由文件共用
- **注意**：如果 6.1 完成了，此步骤即自然解决（改用 Pydantic schema 后不需要手动 format）
- **验证**：删除重复代码，两个路由文件各自 import 同一个函数

#### 6.3 上传时计算 SHA-256

- **文件**：`upload_routes.py`
- **目标**：上传成功后计算文件 SHA-256 哈希，存入 `stored_files.sha256`
- **注意**：大文件需要分块计算（流式），不能全部读入内存。可以用 `hashlib.sha256` 分块读取
- **验证**：`stored_files.sha256` 字段有值

#### 6.4 ProjectLike 加唯一约束

- **文件**：`entities.py` + Alembic 迁移脚本
- **目标**：`__table_args__` 添加 `UniqueConstraint("user_id", "project_id", name="uq_project_like")`
- **验证**：重复点赞在数据库层面报 IntegrityError，应用层捕获

#### 6.5 点赞原子化操作

- **文件**：`project_service.py` 的 `toggle_like` 方法
- **目标**：将 `project.likes += 1` 改为 `UPDATE projects SET likes = likes + 1 WHERE id = :id`
- **验证**：并发测试脚本同时点赞不会丢失计数

#### 6.6 旧字段标记与清理

- **文件**：`entities.py` + `project_service.py`
- **目标**：`Project.report_url`、`image_url` 标记为 deprecated 注释，新代码统一走 `report_file_id` / `stored_files`
- **注意**：不删除字段，只标记 deprecated，保持历史数据兼容
- **验证**：历史作品仍可展示，新作品创建时不写 `report_url`

---

## 执行顺序建议

```
第一轮（修 bug，保障 S3 可运行）：
  P1（批量下载 S3 适配） → P2（S3 适配器修复）
  这两个如果不修，S3 模式根本用不了

第二轮（安全加固）：
  P3（上传安全校验加固）
  堵住 MP4/MOV 魔数漏洞，防止恶意上传

第三轮（测试兜底）：
  P4（测试体系补齐），与 P1-P3 的改造同步写测试

第四轮（体验优化）：
  P5（前端体验优化）

第五轮（代码质量）：
  P6（代码质量与工程化）
  放在最后是因为它不阻塞功能，且 P6.1 schema 改造需要前几步稳定后统一改
```

---

## 风险与依赖

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| P6.1 Schema 落地可能改变 JSON 字段名 | 前端对接出问题 | 改前先做兼容性分析，确保 camelCase 映射正确 |
| P1 批量下载流式改造复杂度高 | Python zipfile 流式写入不直观 | 可先不做完整流式，改为逐个 yield chunk |
| S3 测试需要 moto 库 | 新依赖可能与其他包冲突 | 用独立的 test 依赖组安装 |
| 跨组文件修改（`entities.py`、`teacher_routes.py`） | 可能影响 A/B/D 组 | 只动 C 组相关部分，PR 时标记 review 范围 |
