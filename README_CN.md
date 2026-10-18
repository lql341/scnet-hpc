# scnet-hpc

中文 | [English](README.md)

当前版本：**0.6.13**

```bash
python3 scripts/scnet.py --version
```

<!-- scnet-release:start -->
## 0.6.13 更新

- Windows 凭据条目编码损坏时给出清晰、隐藏秘密的恢复指引。
- 配置结束后提供可从任意目录运行的绝对路径命令，正确处理空格和 shell 特殊字符。
- 将首次使用准备清单同步到两个分发仓库的中英文 README，明确 Windows 原生 OpenAPI
  支持，并为两种目录布局增加文档生成回归检查。
<!-- scnet-release:end -->

`scnet-hpc` 是一个面向 Codex 和 Claude Code 的 SCNet 超算集群技能，通过基于 profile
的 SSH、SCNet OpenAPI 和可插拔 backend 完成集群连接、资源申请、作业生成、运行诊断
和加速器兼容性验证。需要图形客户端时，可从
[SCNet 客户端下载页](https://www.scnet.cn/ui/mall/client/download) 获取官方版本。

## 第一次使用，需要准备什么？

建议先用 **OpenAPI** 完成查询和作业管理；需要远程编译、安装环境或执行 shell 时再配置 SSH。

| 连接方式 | 需要填写 | 从哪里获取 |
| --- | --- | --- |
| OpenAPI（默认） | 平台用户名、AK、SK | 登录 SCNet → 个人中心 → 访问控制 → 生成并下载授权码；AK/SK 分别取文件的 `Accesskey` / `Secretkey` 列 |
| SSH（按需） | 目标集群、集群/Linux 用户名、私钥文件路径 | 控制台选择目标区域 → 命令行 E-Shell → 左上角 SSH 连接 → 下载私钥并核对域名、端口；用户名可用网页 E-Shell 的 `whoami` 核对 |

账号需已开通目标区域资源。两种凭据独立，按当前任务准备即可；阅读说明、离线准备无需凭据。
**AK/SK 只在本机终端的隐藏输入框填写；SSH 填下载文件路径，不要将密钥或私钥正文发到聊天。**

向 Agent 说“帮我首次配置 scnet-hpc”即可；Skill 会先说明所需字段及获取位置，再给当前系统、
实际安装目录对应的本机命令。详见[首次使用清单](references/first-use.md)和下方配置面板。

支持的本地操作系统：

- **Linux**：仓库脚本原生支持；
- **macOS**：仓库脚本原生支持；
- **Windows**：Python OpenAPI 入口可在 PowerShell 使用，并支持 Windows 凭据管理器；
  SSH 自动安装和依赖 Bash、`sed`、`awk` 的完整脚本环境建议通过 WSL2 使用。
  已有 Windows OpenSSH 配置可供 SSH backend 使用；Git Bash 尚未作为完整环境验证。

主要能力：

- 配置 SCNet SSH 连接；
- 通过 SCNet OpenAPI 控制面查询资源和管理标准作业；
- 按集群 profile 生成 CPU 和加速器分区的 Slurm 作业脚本；
- 探测和刷新集群调度规则；
- 区分登录节点与计算节点操作；
- 处理计算节点离线依赖和共享临时目录；
- 验证海光 DCU/DTK 软件兼容性。

当前加速器相关证据主要来自海光 DCU 系统。其他加速器可以复用连接和调度结构，
但其软件能力必须在目标计算节点独立验证。

## 仓库结构

```text
scnet-hpc/
├── VERSION                  同步使用的 SemVer 版本
├── CHANGELOG.md             版本更新记录
├── SKILL.md                 技能入口、路由和操作约束
├── agents/
│   └── openai.yaml          Codex 界面元数据
├── clusters/
│   ├── _template.conf       集群 profile 模板
│   └── <cluster>.conf       纳入版本管理的集群 profile
├── scripts/
│   ├── scnet.py              backend 统一命令行入口
│   ├── scnet_backends/       SSH、OpenAPI 和外部适配器
│   ├── scnet_sdk/            共享 OpenAPI client 和 Notebook 生命周期服务
│   ├── _common.sh           profile 加载和公共函数
│   ├── setup-ssh.sh         SSH 配置
│   ├── new-job.sh           Slurm 脚本生成
│   ├── probe-cluster.sh     初始集群探测
│   ├── refresh-cluster.sh   动态 profile 刷新
│   ├── run-compute-probe.sh 计算节点探针提交
│   ├── setup.sh              配置/维护面板
│   ├── compute-probe.py     加速器能力探针
│   └── install.sh           技能安装
├── references/              按操作类型拆分的参考文档
└── tests/                   脚本回归测试
```

`clusters/` 保留在仓库顶层，因为其中的 profile 是脚本直接读取的运行配置。
`references/` 中的文档仅在对应操作需要时读取。

## 安装

### Agent 一句话安装

把下面这一句话直接发给 Codex：

> 请使用 `$skill-installer` 从 GitHub 仓库 `lql341/scnet-hpc` 的根目录（path `.`）安装 Skill，名称设为 `scnet-hpc`；如果目标已存在则不要覆盖，安装后在安装目录运行 `python3 scripts/scnet.py --help` 验证，并告诉我安装路径。

该提示使用 canonical 仓库，不依赖下游 plugin 仓库。安装完成后，Skill 会在下一轮
对话中可用。

也可以直接运行经过验证的 Codex 官方安装器：

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-installer/scripts/install-skill-from-github.py" \
  --repo lql341/scnet-hpc \
  --path . \
  --name scnet-hpc \
  --method download
```

验证：

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/scnet-hpc/scripts/scnet.py" --help
```

### 从仓库安装

```bash
git clone https://github.com/lql341/scnet-hpc.git
cd scnet-hpc
./scripts/install.sh
```

安装模式：

```bash
./scripts/install.sh --project  # 安装到当前项目
./scripts/install.sh --codex    # 安装到 Codex skills 目录
./scripts/install.sh --claude   # 安装到 Claude Code skills 目录
./scripts/install.sh --link     # 开发模式：链接当前仓库
```

替换已有安装前，脚本会将原目录移动到带时间戳的备份路径。

## 首次使用配置面板

新电脑上可以直接运行：

```bash
./scripts/setup.sh
```

配置面板采用明确的生命周期：

```bash
./scripts/setup.sh new       # 新增连接，不覆盖已有项
./scripts/setup.sh modify    # 修改默认项、轮换 SSH key、刷新 OpenAPI
./scripts/setup.sh status    # 只读查看配置
./scripts/setup.sh reset     # 分范围重置，不默认删除真实 SSH key
```

Bash 面板可以重复运行，用于选择默认 profile、更新某个区域的 SSH 用户和私钥，并检查
密钥文件名中的有效期；
默认 OpenAPI 配置需要 Python 3。没有 Python 时仅支持首次 SSH 配置；更新已有主配置需要
Python 3，以保留其他字段。首次进入默认选择 `new`，已有配置默认选择 `modify`；
backend 默认使用已有选择，没有选择时使用 OpenAPI。非敏感主配置保存到
`~/.config/scnet-hpc/config.json`（或 `$XDG_CONFIG_HOME/scnet-hpc/config.json`），
SSH 和 OpenAPI 区域元数据分别保存到同目录下的 `ssh/<profile>.json` 和 `openapi.json`，
不会保存 AK、SK 或 token。

OpenAPI 只需要配置一次平台用户名、AK 和 SK；区域 ID、区域用户名和调度器会自动发现。
开发者也可以使用功能更完整的 Python 面板，它会验证凭据并发现所有授权区域：

```bash
python3 scripts/scnet.py setup
```

无需先手写环境变量：进入向导后逐项粘贴三个字段的值，AK/SK 均不回显。向导会检查误粘贴的
赋值命令、换行和不可见字符；保存后读回验证，并显示真实保存状态。

| 系统 | AK/SK 持久保存 | 需要准备什么 |
|---|---|---|
| macOS | 系统 Keychain | 无额外依赖；按系统提示解锁/授权 |
| Linux 桌面 | Secret Service | `secret-tool` 加运行且已解锁的密钥环；Ubuntu/Debian 可安装 `libsecret-tools` |
| Linux 服务器 / 无桌面 | 可由宿主注入环境变量 | 不强制安装 `libsecret-tools`；安装工具不等于密钥环服务可用 |
| Windows PowerShell | 当前用户的 Windows 凭据管理器 | Python 3，无额外密钥环依赖 |

Windows 使用 `python scripts/scnet.py setup new --mode openapi`。环境变量优先于系统凭据库；
PowerShell 的 `$env:` 赋值只影响当前窗口及其后启动的子进程，已打开的桌面应用不会自动获得。
具体命令、查看/删除位置见 [`references/openapi.md`](references/openapi.md)。

Notebook 已作为独立服务域接入，支持只读查询和确认驱动的生命周期操作：

```bash
python3 scripts/scnet.py --backend openapi notebook regions
python3 scripts/scnet.py --backend openapi --region 11250 notebook resources
python3 scripts/scnet.py --backend openapi --region 11250 notebook images
python3 scripts/scnet.py --backend openapi --region 11250 notebook list
python3 scripts/scnet.py --dry-run --backend openapi \
  notebook create --region 11250
python3 scripts/scnet.py --backend openapi \
  notebook smoke --region 11250
```

Notebook 默认脱敏 SSH 密码和带查询凭据的 URL。创建时自动选择当前最小可用资源和
官方预置 Jupyter 镜像。所有变更操作需要确认；非交互调用必须显式传入 `--yes`。
`smoke` 会在验证后自动关机和释放。

OpenAPI 区域支持多选：使用 ↑/↓ 移动、Space 勾选、`a` 全选、Enter 保存。多选表示
“在本机启用的区域”；其中仍需单选一个默认区域。作业提交始终要求唯一目标区域，避免
一次操作在多个中心重复提交。

AK/SK 获取路径：登录 SCNet，进入“个人中心 → 访问控制”，生成并下载授权码。配置面板
支持 ↑/↓ 移动并按 Enter 确认，也可以输入数字后按 Enter；直接按 Enter 使用当前默认项。
macOS Terminal、Ubuntu Terminal 和 Debian Terminal 的操作方式相同。Ubuntu/Debian
可用 `sudo apt install libsecret-tools` 安装 Secret Service 命令行工具，保存时还需密钥环服务运行
并解锁；如果通过环境变量提供凭据，则无需安装。

配置后可以只读检查：

```bash
python3 scripts/scnet.py doctor
python3 scripts/scnet.py --backend openapi doctor
```

使用 `./scripts/setup.sh --skip-connect` 可以只保存选择，不安装私钥，也不连接远端服务。单次命令仍可
通过 `--backend` 覆盖默认 backend。

## 选择集群

```bash
ls clusters/*.conf
sed -n '1,220p' clusters/<cluster>.conf
```

profile 包含连接地址、调度限制、分区、硬件、module、网络观测和已知限制。
动态探测结果写入 `clusters/.cache/<cluster>.auto.conf`，并覆盖 profile 中的同名字段。
存在多个 profile 时，应显式传入 `--cluster <name>`。

## 选择 backend

OpenAPI AK/SK 是结构化集群操作的优先 backend；SSH 继续用于环境配置、编译、交互式诊断
和其他 shell 工作流。查看内置和已发现的 backend：

```bash
python3 scripts/scnet.py backends
```

示例：

```bash
python3 scripts/scnet.py --backend ssh --cluster <cluster> queues
python3 scripts/scnet.py --backend openapi clusters
python3 scripts/scnet.py --backend openapi --region <region-id> job <job-id>
```

选择优先级为：显式 `--backend`、`SCNET_HPC_BACKEND`、配置面板保存的默认 backend、
profile 中的 `DEFAULT_BACKEND`、最后回退到 `openapi`。需要 SSH 时使用 `--backend ssh`。
一个 backend 失败时不会静默切换到另一个。

OpenAPI 凭据通过环境变量或宿主凭据管理器注入；不得把 AK、SK 或 token 写入 profile。
具体配置见 [`references/openapi.md`](references/openapi.md)。未来 MCP bridge、官方
连接器或其他平台连接方式可以通过
[`references/backends.md`](references/backends.md) 中的外部 backend 协议注册。

OpenAPI backend 现在支持创建远端目录，超过 8 MiB 的文件会自动使用官方分片上传流程。
可以通过 `--dry-run` 预览提交、取消、目录创建和文件传输操作，而不连接 backend。

## 配置 SSH

SSH 使用目标集群控制台下载的私钥文件，和 OpenAPI AK/SK 分开配置。用户名是区域内的
集群/Linux 用户名，可能与平台登录名不同。向导会先显示连接目标、私钥目标位置及已有配置的
处理方式；只需输入文件路径，不要粘贴私钥内容，也不要选择 `.pub` 公钥。

从 SCNet 控制台取得私钥后执行：

```bash
./scripts/setup-ssh.sh --cluster <cluster> <private-key-file> <username>
```

脚本会将私钥复制到 `~/.ssh/id_rsa_<cluster>`，在别名尚未配置时追加 SSH host，
设置连接复用和保活，并验证连接。脚本不会覆盖已有的 SSH host 配置。
手工配置和故障处理见 [`references/setup.md`](references/setup.md)。

在 Windows 上通过 WSL2 使用时，私钥和 `~/.ssh/config` 位于 WSL 文件系统中，
与 Windows 原生 SCNet 客户端或 Windows OpenSSH 的配置相互独立。

## 生成作业

```bash
./scripts/new-job.sh --cluster <cluster> train 1 8 00:20:00
./scripts/new-job.sh --cluster <cluster> --cpu-only build 0 32 01:00:00
./scripts/new-job.sh --cluster <cluster> --partition <partition> probe 1 8 00:10:00
```

生成器根据 `DEF_MEM_PER_CPU` 计算保守内存值，应用 profile 中的 GRES 和 module，
在需要时设置离线环境变量，将临时文件放入共享家目录，并传播工作负载退出码。

提交前检查生成的 `.slurm` 文件。目标集群支持时，先通过 `sbatch --test-only`
验证调度参数；只有实际需要提交时才移除 `--test-only`。

## 刷新 profile

```bash
./scripts/refresh-cluster.sh --cluster <cluster>
./scripts/refresh-cluster.sh --cluster <cluster> --compute
./scripts/refresh-cluster.sh --cluster <cluster> --dry-run
```

默认刷新只在登录节点执行只读探测。`--compute` 会提交小型 Slurm 作业并消耗集群资源。

## 新增集群

建立可用的临时 SSH 别名后执行：

```bash
./scripts/probe-cluster.sh <ssh-alias> <cluster-name> \
  > clusters/<cluster-name>.conf
```

补齐登录节点无法确认的字段，尤其是加速器架构、module、CPU 分区行为和计算节点网络。
随后配置正式 SSH 别名，并运行有明确资源和时间上限的验证作业。完整流程见
[`references/adding-cluster.md`](references/adding-cluster.md)。

## 参考文档

| 文档 | 内容 |
|---|---|
| [`setup.md`](references/setup.md) | SSH 配置和连接故障 |
| [`environment.md`](references/environment.md) | module、Python 环境、依赖和存储 |
| [`troubleshooting.md`](references/troubleshooting.md) | Slurm、日志、运行时、网络和加速器故障 |
| [`adding-cluster.md`](references/adding-cluster.md) | profile 创建和集群验证 |
| [`hygon-dcu-development.md`](references/hygon-dcu-development.md) | 海光 DCU/DTK 开发资料 |
| [`software-compatibility.md`](references/software-compatibility.md) | 兼容性验证和公开报告 |
| [`quickstart-en.md`](references/quickstart-en.md) | 英文快速操作指南 |
| [`backends.md`](references/backends.md) | backend 选择、能力和扩展协议 |
| [`openapi.md`](references/openapi.md) | OpenAPI 凭据、命令和验证边界 |
| [`notebook.md`](references/notebook.md) | Notebook 查询、生命周期和敏感字段脱敏 |

## 验证

```bash
bash tests/test-new-job.sh
python3 tests/test-backends.py
```

本地测试覆盖作业生成、profile 解析、OpenAPI 签名与响应归一化，以及外部 backend
协议；不会提交远端作业，也不会访问真实 OpenAPI。

## 安全与公开发布

不得提交私钥、访问令牌、个人用户名、内部主机名、节点名、作业编号、私有镜像地址，
以及包含用户路径的生成作业脚本。公开兼容性报告应保留可复现的环境和结果数据，
并将可识别基础设施的信息替换为占位符。

## 许可证

本项目采用 [MIT License](LICENSE) 开源。除许可证正文另有规定外，使用者可以自由使用、复制、修改、合并、发布、再许可和销售本项目及其衍生作品。

再发布本项目或其重要组成部分时，应保留版权声明和 MIT 许可声明。本项目按“现状”提供，不对适销性、特定用途适用性或不侵权作任何明示或默示保证；使用者应自行评估代码、脚本、集群配置和生成结果的适用性及风险。

## 版本管理

源 Skill、DSH package 和 Codex Plugin 使用同一套 SemVer 版本。根目录 `VERSION` 是唯一
版本来源；每次更新中英文 `RELEASE_HIGHLIGHTS` 当前版本摘要后，运行
`python3 .github/scripts/release_docs.py`。CI 会检查生成的 README 区块、同步两个分发
仓库，并在校验通过后发布对应的 Git tag、GitHub Release 与 npm package。完整历史
保留在 [CHANGELOG.md](CHANGELOG.md)。

## 精简输出与等待

默认作业查询只返回 ID、状态、队列，以及存在的退出码或失败原因；空字段被省略，
`0` 和 `false` 保留。`--details` 返回完整归一化字段，`--raw` 返回 backend 原始数据。
`--json` 保留 JSON 信封，默认使用紧凑格式；`--dry-run` 始终保留完整预览。

```bash
python3 scripts/scnet.py --region <id> job <job-id>
python3 scripts/scnet.py --details --region <id> job <job-id>
python3 scripts/scnet.py --region <id> wait <job-id> --interval 3 --wait-timeout 180
```

`wait` 在程序内部轮询，只输出最终结果或超时摘要。OpenAPI 实时接口的 `COMPLETED`
可能对应刚取消的作业；历史记录未确认前显示 `FINALIZING`，因此等待可能受账本更新延迟影响。
传输结果默认返回目标路径和字节数，日志仅返回请求的日志行。调用方若需要旧版完整字段，
请显式添加 `--details`。SDK/backend 返回结构不受 CLI 精简影响。
