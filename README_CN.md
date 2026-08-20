# scnet-hpc

中文 | [English](README.md)

`scnet-hpc` 是一个面向 Codex 和 Claude Code 的 SCNet 超算集群技能，通过基于 profile
的 SSH 与 Slurm 工作流完成集群连接、资源申请、作业生成、运行诊断和加速器兼容性
验证。需要图形客户端时，可从
[SCNet 客户端下载页](https://www.scnet.cn/ui/mall/client/download) 获取官方版本。

支持的本地操作系统：

- **Linux**：仓库脚本原生支持；
- **macOS**：仓库脚本原生支持；
- **Windows**：官方 SCNet 客户端支持 Windows 10 及以上，但本仓库依赖 Bash、SSH、
  `sed`、`awk` 等 Unix 工具，不提供 Windows 原生脚本入口。建议通过 WSL2 使用；
  Git Bash 可能支持部分命令，但尚未作为完整环境验证。

主要能力：

- 配置 SCNet SSH 连接；
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
├── SKILL.md                 技能入口、路由和操作约束
├── agents/
│   └── openai.yaml          Codex 界面元数据
├── clusters/
│   ├── _template.conf       集群 profile 模板
│   └── <cluster>.conf       纳入版本管理的集群 profile
├── scripts/
│   ├── _common.sh           profile 加载和公共函数
│   ├── setup-ssh.sh         SSH 配置
│   ├── new-job.sh           Slurm 脚本生成
│   ├── probe-cluster.sh     初始集群探测
│   ├── refresh-cluster.sh   动态 profile 刷新
│   ├── run-compute-probe.sh 计算节点探针提交
│   ├── compute-probe.py     加速器能力探针
│   └── install.sh           技能安装
├── references/              按操作类型拆分的参考文档
└── tests/                   脚本回归测试
```

`clusters/` 保留在仓库顶层，因为其中的 profile 是脚本直接读取的运行配置。
`references/` 中的文档仅在对应操作需要时读取。

## 安装

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

## 选择集群

```bash
ls clusters/*.conf
sed -n '1,220p' clusters/<cluster>.conf
```

profile 包含连接地址、调度限制、分区、硬件、module、网络观测和已知限制。
动态探测结果写入 `clusters/.cache/<cluster>.auto.conf`，并覆盖 profile 中的同名字段。
存在多个 profile 时，应显式传入 `--cluster <name>`。

## 配置 SSH

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

## 验证

```bash
bash tests/test-new-job.sh
```

本地测试覆盖加速器作业、CPU-only 作业、显式分区和非法输入，不会提交远端作业。

## 安全与公开发布

不得提交私钥、访问令牌、个人用户名、内部主机名、节点名、作业编号、私有镜像地址，
以及包含用户路径的生成作业脚本。公开兼容性报告应保留可复现的环境和结果数据，
并将可识别基础设施的信息替换为占位符。

## 许可证

本项目采用 [MIT License](LICENSE) 开源。除许可证正文另有规定外，使用者可以自由使用、复制、修改、合并、发布、再许可和销售本项目及其衍生作品。

再发布本项目或其重要组成部分时，应保留版权声明和 MIT 许可声明。本项目按“现状”提供，不对适销性、特定用途适用性或不侵权作任何明示或默示保证；使用者应自行评估代码、脚本、集群配置和生成结果的适用性及风险。
