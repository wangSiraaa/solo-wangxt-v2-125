# plume-lab · 离线高斯烟羽情景教学应用

面向环境课程的**离线**教学应用，展示**烟囱高度、风速、大气稳定度**如何影响
地面污染物浓度。

> ⚠ **使用边界**：本系统所有排放源与气象数据均为虚构；采用平坦地形、稳态风
> 假设与教科书级 Briggs（乡村）扩散系数。结果**只用于课堂概念理解**，
> **不得用于真实事故应急预警，也不得用于法规达标判定**。

## 技术栈

| 层 | 技术 | 说明 |
|---|---|---|
| 前端 | Vue 3 + Vite + MapLibre GL JS + d3-contour | 等值面（marching squares）绘制在**离散采样格点**上；无任何在线瓦片，底图为自绘经纬网 |
| 后端 | FastAPI + NumPy | 显式参数化的稳态高斯烟羽模型（全部经验常数集中在 `dispersion.py`） |
| 数据库 | PostgreSQL + PostGIS | 虚构排放源/气象情景；lon/lat→Web Mercator 投影在库内完成并提供往返核对视图 |

## 模型与约定

```
C(x,y,z) = Q / (2π u σy σz) · exp(-y²/2σy²)
           · [ exp(-(z-H)²/2σz²) + exp(-(z+H)²/2σz²) ]
```

- `x` 下风向（沿输送去向为正），`y` 横风向（面向下风向左侧为正），
  `H = hs + Δh` 为有效源高，`u` 为 H 高度风速（10 m 风速经幂指数廓线换算）。
- **风向约定可检查**：气象风向 = 风的来向（0=北，顺时针）；
  输送方位 = 来向 + 180°。API `/api/wind-geometry` 给出四个方向检查点。
- **静风不硬算**：10 m 风速 < 0.5 m/s 直接返回 `422 CALM_WIND`。
  公式在 u→0 时发散，这不是物理上的"无限浓度"，而是模型失效。
- **有效距离**：Briggs 乡村曲线经验区间 x ∈ [100, 10000] m；
  区间外格点输出 `null`（NaN），地图上不做静默外推。
- **单位分开展示**：源项（g/s、g/h、kg/d）、背景值（µg/m³）、
  烟羽贡献三者在界面上分栏；色图只画烟羽贡献。
- **网格分辨率不改变输入**：分辨率只改变采样/展示密度；
  轴线剖面用独立固定采样，接口测试断言换分辨率时源项、风速、有效源高不变。
- **地图表达采样而非无限精度**：虚线框为采样范围，可叠加格点中心，
  等值面不平滑（`smooth(false)`），色带为有限固定等级。

## 解析核对用例（`/api/verification`）

1. **A 横风向对称性**：`C(x,+y)=C(x,-y)`（y 只以 y² 入式）
2. **B 下风向衰减**：高架源地面轴线浓度先升后降，峰后单调衰减
3. **C 源高效应**：同 Q 同气象，源越高地面峰值越低、峰值落地越远
4. **D 风向几何**：来向↔去向相差 180°，北风向南输送

## 快速启动（无 root，用户目录 PostgreSQL+PostGIS）

仓库提供 `scripts/`：

```bash
# 1) 下载并解压 PostgreSQL 15 + PostGIS 3 到 /tmp/pglocal，初始化并启动
./scripts/setup_db.sh

# 2) 启动后端（自动建表、建 PostGIS 扩展、写入虚构数据）
./scripts/run_backend.sh

# 3) 启动前端开发服务器（另一个终端）
cd frontend && npm install && npm run dev
#   或构建后由 FastAPI 直接托管：npm run build，然后访问 http://127.0.0.1:8000/
```

默认连接：`postgresql://plume@/plume_lab?host=/tmp&port=55432`，
可用环境变量 `PLUME_DSN` 覆盖。

## 测试

```bash
cd backend
python3 -m pytest tests/ -q
# 31 个模型数值测试 + 11 个 API/PostGIS 端到端测试
```

## 主要 API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 服务/PostGIS 版本与数据计数 |
| GET | `/api/config` | 全部经验系数、有效范围、单位、风向约定、静风策略 |
| GET | `/api/sources` `/api/met` | 虚构源与气象情景 |
| GET | `/api/sources/geojson` | PostGIS 输出的源 GeoJSON |
| GET | `/api/coordinate-check` | 4326→3857→4326 往返误差 |
| GET | `/api/wind-geometry?wind_from_deg=180` | 风向转换与检查点坐标 |
| POST | `/api/plume` | 提交情景+采样网格，返回浓度矩阵、分解项与剖面 |
| GET | `/api/verification` | 四个解析核对用例结果 |

## 目录

```
plume-lab/
├── backend/app/
│   ├── dispersion.py    # 显式参数：Briggs 系数、风廓线指数、范围常量
│   ├── gaussian.py      # 高斯烟羽公式、网格、静风/范围策略
│   ├── verification.py  # 解析核对用例
│   ├── db.py schema.sql seed_data.py
│   └── main.py          # FastAPI
├── frontend/src/
│   ├── App.vue components/{ControlPanel,MapPanel,ResultsPanel}.vue
│   ├── geo.js           # 网格→等值面 GeoJSON（d3-contour）
│   └── api.js
└── scripts/
```
